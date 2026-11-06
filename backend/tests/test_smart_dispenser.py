"""Smart containers, food identification, Generate My Meal / Serve Meal, accuracy and auto-tuning.
The ESP32 is SIMULATED with HTTP calls following the firmware protocol."""
import base64
import uuid

import pytest

from app.models.device import ContainerFoodAssignment, DeviceContainer
from app.services import usda_client
from tests.conftest import PROFILE, find_food, register_user
from tests.test_dispenser import FakeESP32

API = "/api/v1"
PNG_1PX = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000154a24f"
    "5d0000000049454e44ae426082") * 2).decode()


@pytest.fixture
def rig(client, profiled):
    """A paired, online dispenser with 3 containers: raw rice, egg, almonds."""
    created = client.post(f"{API}/devices", json={"name": "Kitchen"}, headers=profiled).json()
    did = created["device"]["id"]
    esp = FakeESP32(client, did, created["device_token"])
    esp.register(servo_count=4)
    esp.heartbeat()
    containers = []
    for slot, food in enumerate(["White rice, raw (dry)", "Egg, whole, boiled", "Almonds"], start=1):
        c = client.post(f"{API}/devices/{did}/containers", headers=profiled, json={
            "slot_number": slot, "servo_channel": slot - 1, "label": f"Container {slot}",
            "open_angle": 70, "closed_angle": 0}).json()
        f = find_food(client, profiled, food)
        c = client.put(f"{API}/devices/{did}/containers/{c['id']}/food", headers=profiled,
                       json={"food_item_id": f["id"], "confirm": True}).json()
        containers.append(c)
    return {"auth": profiled, "did": did, "esp": esp, "containers": containers}


def run_device(esp, results):
    """Let the fake ESP32 execute queued commands; results = list of (status, grams_or_factor, error_code)."""
    seen = []
    for status, grams, code in results:
        r = esp.next()
        assert r.status_code == 200, "expected a command for the device"
        cmd = r.json()
        seen.append(cmd)
        esp.ack(cmd["command_id"])
        measured = grams(cmd["target_weight_g"]) if callable(grams) else grams
        extra = {"error_code": code} if code else {}
        esp.result(cmd["command_id"], status=status, dispensed=measured, **extra)
    return seen


# ---- identification and classification -------------------------------------------

def test_identify_prefers_dispenser_friendly_and_classifies(client, auth):
    r = client.get(f"{API}/foods/identify", params={"q": "rice"}, headers=auth).json()
    first = r["candidates"][0]
    assert first["name"] == "White rice, raw (dry)" and first["dispenser_friendly"] is True
    assert first["categories"] == ["carbohydrates"] and first["calories_per_100g"] == 365
    assert r["external_provider"] is None  # no USDA key configured in tests


def test_identify_understands_local_names(client, auth):
    egg = client.get(f"{API}/foods/identify", params={"q": "anda"}, headers=auth).json()["candidates"][0]
    assert egg["name"] == "Egg, whole, boiled" and egg["categories"] == ["protein", "fat"]
    oats = client.get(f"{API}/foods/identify", params={"q": "oats"}, headers=auth).json()["candidates"][0]
    assert oats["categories"] == ["carbohydrates", "protein", "fiber"]
    none = client.get(f"{API}/foods/identify", params={"q": "zzqqx"}, headers=auth).json()
    assert none["candidates"] == []


def test_usda_parser_validates_records():
    good = {"fdcId": 123, "description": "RICE, WHITE, LONG-GRAIN, RAW", "dataType": "SR Legacy", "foodNutrients": [
        {"nutrientId": 1008, "value": 365, "unitName": "KCAL"}, {"nutrientId": 1003, "value": 7.13},
        {"nutrientId": 1004, "value": 0.66}, {"nutrientId": 1005, "value": 79.95}, {"nutrientId": 1079, "value": 1.3}]}
    food = usda_client.parse_food(good)
    assert food and food.calories == 365 and food.fdc_id == "123" and "FDC ID 123" in food.source
    foundation = {**good, "foodNutrients": [{"nutrientId": 2047, "value": 360, "unitName": "KCAL"},
                                            *good["foodNutrients"][1:]]}
    assert usda_client.parse_food(foundation).calories == 360
    assert usda_client.parse_food({**good, "foodNutrients": good["foodNutrients"][1:]}) is None  # no energy
    impossible = {**good, "foodNutrients": [{"nutrientId": 1008, "value": 50}, *good["foodNutrients"][1:]]}
    assert usda_client.parse_food(impossible) is None  # 50 kcal can't hold 80 g carbs


def test_usda_import_refetches_and_is_private(client, auth, monkeypatch):
    monkeypatch.setattr(usda_client, "enabled", lambda: True)
    monkeypatch.setattr(usda_client, "get", lambda fid: usda_client.UsdaFood(
        fdc_id=fid, name="Quinoa, uncooked", data_type="SR Legacy", calories=368, protein=14.1, carbs=64.2,
        fat=6.1, fiber=7.0))
    r = client.post(f"{API}/foods/import", headers=auth, json={"external_id": "168874", "diet_type": "vegan"})
    assert r.status_code == 201
    food = r.json()
    assert food["is_custom"] and not food["is_approximate"] and "FDC ID 168874" in food["source"]
    assert food["categories"] == ["carbohydrates", "protein", "fiber"]
    again = client.post(f"{API}/foods/import", headers=auth, json={"external_id": "168874"}).json()
    assert again["id"] == food["id"]  # imported once per user
    other, _ = register_user(client)
    assert client.get(f"{API}/foods/{food['id']}", headers=other).status_code == 404


# ---- containers ---------------------------------------------------------------------

def test_container_assignment_needs_confirmation_and_keeps_history(client, rig, db):
    c = rig["containers"][0]
    assert c["food"]["categories"] == ["carbohydrates"] and c["food"]["protein_per_100g"] == 7.1
    oats = find_food(client, rig["auth"], "Rolled oats (dry)")
    url = f"{API}/devices/{rig['did']}/containers/{c['id']}/food"
    assert client.put(url, headers=rig["auth"], json={"food_item_id": oats["id"], "confirm": False}).status_code == 422
    r = client.put(url, headers=rig["auth"], json={"food_item_id": oats["id"], "confirm": True, "label": "Oats jar"})
    assert r.status_code == 200 and r.json()["food"]["name"] == "Rolled oats (dry)" and r.json()["label"] == "Oats jar"
    rows = db.query(ContainerFoodAssignment).filter_by(container_id=uuid.UUID(c["id"])).all()
    assert len(rows) == 2 and sum(1 for x in rows if x.removed_at is None) == 1


def test_container_photo_upload_and_public_url(client, rig):
    c = rig["containers"][0]
    url = f"{API}/devices/{rig['did']}/containers/{c['id']}/image"
    r = client.put(url, headers=rig["auth"], json={"image_base64": "data:image/png;base64," + PNG_1PX})
    assert r.status_code == 200 and r.json()["image_url"].startswith("/api/v1/media/containers/")
    img = client.get(r.json()["image_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    bad = client.put(url, headers=rig["auth"], json={"image_base64": base64.b64encode(b"<script>" * 40).decode()})
    assert bad.status_code == 422
    other, _ = register_user(client)
    assert client.put(url, headers=other, json={"image_base64": PNG_1PX}).status_code == 404
    assert client.delete(url, headers=rig["auth"]).json()["image_url"] is None


# ---- Generate My Meal ------------------------------------------------------------------

def test_generate_meal_uses_all_macros_and_stays_within_targets(client, rig):
    r = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                    json={"device_id": rig["did"], "meal_type": "lunch"})
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["status"] == "proposed" and plan["items"]
    target, est = plan["meal_target"], plan["estimated_totals"]
    assert est["kcal"] <= plan["remaining_today"]["kcal"]
    assert abs(est["kcal"] - target["kcal"]) <= 0.25 * target["kcal"]
    for item in plan["items"]:
        assert 10 <= item["grams"] <= 500 and item["grams"] % 5 == 0 and item["reasons"]
    egg = next((i for i in plan["items"] if i["food_name"].startswith("Egg")), None)
    if egg:
        assert egg["grams"] <= 150  # max 3 servings
        assert egg["nutrition"]["fat"] > 0 and egg["nutrition"]["protein"] > 0


def test_generate_respects_diet_and_allergies(client, rig):
    client.put(f"{API}/profile", headers=rig["auth"], json={**PROFILE, "dietary_preference": "vegan",
                                                            "allergies": ["tree_nut"]})
    plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                       json={"device_id": rig["did"], "meal_type": "lunch"}).json()
    names = [i["food_name"] for i in plan["items"]]
    assert names == ["White rice, raw (dry)"]
    assert any("Egg" in s and "vegan" in s for s in plan["skipped"])
    assert any("Almonds" in s and "tree_nut" in s for s in plan["skipped"])


def test_serve_meal_runs_in_sequence_and_logs_measured_weights(client, rig):
    plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                       json={"device_id": rig["did"], "meal_type": "dinner"}).json()
    items = [{"container_id": c["id"], "grams": g} for c, g in zip(rig["containers"], (100, 100, 20))]
    served = client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"], json={"items": items})
    assert served.status_code == 200, served.text
    statuses = [i["command"]["status"] for i in served.json()["items"]]
    assert statuses == ["pending", "queued", "queued"]
    # a retry of Serve doesn't create more commands
    again = client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"], json={"items": items})
    assert [i["command"]["id"] for i in again.json()["items"]] == [i["command"]["id"] for i in served.json()["items"]]

    seen = run_device(rig["esp"], [("completed", 108.0, None), ("completed", 120.0, None), ("completed", 19.0, None)])
    assert [s["meal_position"] for s in seen] == [1, 2, 3] and seen[0]["meal_total"] == 3
    assert seen[0]["label"] == "White rice, raw (dry)"

    final = client.get(f"{API}/dispenser/meal-plans/{plan['id']}", headers=rig["auth"]).json()
    assert final["status"] == "completed"
    rice, egg, almonds = final["items"]
    assert rice["command"]["accuracy"] == "within_tolerance" and rice["command"]["difference_g"] == 8.0
    assert egg["command"]["accuracy"] == "over" and egg["command"]["difference_percent"] == 20.0
    assert egg["command"]["nutrition"]["calories"] == pytest.approx(155 * 1.2, abs=0.1)  # 120 g, not 100 g
    daily = client.get(f"{API}/meals/daily", headers=rig["auth"]).json()
    dinner = next(g for g in daily["meals"] if g["meal_type"] == "dinner")["entries"]
    assert sorted(e["quantity_g"] for e in dinner) == [19.0, 108.0, 120.0]
    assert all(e["source"] == "dispenser" for e in dinner)
    assert final["measured_totals"]["grams"] == 247.0


def test_meal_continues_after_empty_container_but_stops_on_sensor_failure(client, rig):
    def serve_all():
        plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                           json={"device_id": rig["did"], "meal_type": "lunch"}).json()
        items = [{"container_id": c["id"], "grams": 50} for c in rig["containers"]]
        return client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"],
                           json={"items": items}).json()["id"]

    pid = serve_all()
    run_device(rig["esp"], [("failed", 3.0, "no_flow"), ("completed", 50.0, None), ("completed", 50.0, None)])
    p = client.get(f"{API}/dispenser/meal-plans/{pid}", headers=rig["auth"]).json()
    assert p["status"] == "partial" and [i["command"]["status"] for i in p["items"]] == ["failed", "completed", "completed"]

    pid = serve_all()
    run_device(rig["esp"], [("failed", None, "sensor_timeout")])
    p = client.get(f"{API}/dispenser/meal-plans/{pid}", headers=rig["auth"]).json()
    assert [i["command"]["status"] for i in p["items"]] == ["failed", "cancelled", "cancelled"]
    assert p["status"] == "failed" and rig["esp"].next().status_code == 204


def test_emergency_stop_and_stop_meal(client, rig):
    plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                       json={"device_id": rig["did"], "meal_type": "lunch"}).json()
    items = [{"container_id": c["id"], "grams": 40} for c in rig["containers"]]
    client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"], json={"items": items})
    first = rig["esp"].next().json()
    rig["esp"].ack(first["command_id"])
    client.post(f"{API}/devices/{rig['did']}/emergency-stop", headers=rig["auth"], json={})
    assert rig["esp"].progress(first["command_id"], 10).json()["abort"] is True
    rig["esp"].result(first["command_id"], status="cancelled", dispensed=11.0, error_code="emergency_stop")
    p = client.get(f"{API}/dispenser/meal-plans/{plan['id']}", headers=rig["auth"]).json()
    assert [i["command"]["status"] for i in p["items"]] == ["cancelled", "cancelled", "cancelled"]
    assert p["status"] == "failed"  # nothing completed, nothing logged
    client.post(f"{API}/devices/{rig['did']}/emergency-stop/reset", headers=rig["auth"])

    plan2 = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                        json={"device_id": rig["did"], "meal_type": "lunch"}).json()
    client.post(f"{API}/dispenser/meal-plans/{plan2['id']}/serve", headers=rig["auth"], json={"items": items})
    stopped = client.post(f"{API}/dispenser/meal-plans/{plan2['id']}/stop", headers=rig["auth"]).json()
    assert stopped["status"] == "cancelled" and rig["esp"].next().status_code == 204


def test_device_busy_while_meal_queued_and_outdated_plan(client, rig):
    plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                       json={"device_id": rig["did"], "meal_type": "lunch"}).json()
    oats = find_food(client, rig["auth"], "Rolled oats (dry)")
    first = plan["items"][0]
    client.put(f"{API}/devices/{rig['did']}/containers/{first['container_id']}/food", headers=rig["auth"],
               json={"food_item_id": oats["id"], "confirm": True})
    r = client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"], json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "plan_outdated"

    plan = client.post(f"{API}/dispenser/meal-plans", headers=rig["auth"],
                       json={"device_id": rig["did"], "meal_type": "lunch"}).json()
    client.post(f"{API}/dispenser/meal-plans/{plan['id']}/serve", headers=rig["auth"], json={})
    single = client.post(f"{API}/dispenser/commands", headers={**rig["auth"], "Idempotency-Key": uuid.uuid4().hex},
                         json={"device_id": rig["did"], "container_id": rig["containers"][0]["id"],
                               "target_weight_g": 50, "meal_type": "snacks"})
    assert single.status_code == 409 and single.json()["error"]["code"] == "device_busy"


def test_auto_tune_learns_close_early_amount(client, rig, db):
    c = rig["containers"][0]
    cmd = client.post(f"{API}/dispenser/commands", headers={**rig["auth"], "Idempotency-Key": uuid.uuid4().hex},
                      json={"device_id": rig["did"], "container_id": c["id"], "target_weight_g": 100,
                            "meal_type": "snacks"}).json()
    sent = rig["esp"].next().json()
    assert sent["settings"]["inflight_g"] == 8 and sent["settings"]["tolerance_percent"] == 10
    rig["esp"].ack(cmd["id"])
    rig["esp"].result(cmd["id"], dispensed=120.0)  # 20 g too much
    learned = client.get(f"{API}/devices/{rig['did']}", headers=rig["auth"]).json()["containers"][0]
    assert learned["learned_inflight_g"] == 18.0  # 8 + 0.5 x 20
    client.post(f"{API}/dispenser/commands", headers={**rig["auth"], "Idempotency-Key": uuid.uuid4().hex},
                json={"device_id": rig["did"], "container_id": c["id"], "target_weight_g": 100, "meal_type": "snacks"})
    assert rig["esp"].next().json()["settings"]["inflight_g"] == 18.0
