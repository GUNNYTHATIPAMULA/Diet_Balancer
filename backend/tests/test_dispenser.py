"""End-to-end dispenser protocol tests. The ESP32 is simulated with HTTP calls
that follow the same sequence as the firmware: register -> heartbeat -> poll
next -> ack -> progress -> result. These are SIMULATED tests, not hardware tests."""
import uuid
from datetime import timedelta

import pytest

from app.models.device import DispensingCommand
from app.utils.time import utcnow
from tests.conftest import find_food, register_user

API = "/api/v1"


class FakeESP32:
    def __init__(self, client, device_id, token):
        self.client, self.id = client, device_id
        self.h = {"X-Device-Token": token}
        self.hh = {"X-Device-Id": device_id, "X-Device-Token": token}

    def register(self, **overrides):
        body = {"firmware_version": "1.0.0", "servo_count": 2, "hx711_ready": True, "oled_ready": True,
                "calibrated": True, "ip_address": "192.168.1.50", "wifi_rssi": -55, **overrides}
        return self.client.post(f"{API}/devices/register", json=body, headers=self.hh)

    def heartbeat(self, weight=0.0, state="idle"):
        return self.client.post(f"{API}/devices/heartbeat", json={"state": state, "weight_g": weight,
                                                                  "hx711_ready": True}, headers=self.hh)

    def next(self):
        return self.client.get(f"{API}/devices/{self.id}/commands/next", headers=self.h)

    def ack(self, cid):
        return self.client.post(f"{API}/devices/{self.id}/commands/{cid}/ack", headers=self.h)

    def progress(self, cid, weight):
        return self.client.post(f"{API}/devices/{self.id}/commands/{cid}/progress",
                                json={"weight_g": weight}, headers=self.h)

    def result(self, cid, status="completed", dispensed=97.4, **extra):
        body = {"status": status, "start_weight_g": 0.0, "final_weight_g": dispensed,
                "dispensed_weight_g": dispensed, "duration_ms": 8100, **extra}
        return self.client.post(f"{API}/devices/{self.id}/commands/{cid}/result", json=body, headers=self.h)


@pytest.fixture
def setup(client, auth):
    created = client.post(f"{API}/devices", json={"name": "Kitchen dispenser"}, headers=auth)
    assert created.status_code == 201
    device = created.json()["device"]
    esp = FakeESP32(client, device["id"], created.json()["device_token"])
    assert esp.register().status_code == 200
    assert esp.heartbeat().status_code == 200
    rice = find_food(client, auth, "White rice, raw (dry)")
    container = client.post(f"{API}/devices/{device['id']}/containers", headers=auth, json={
        "slot_number": 1, "servo_channel": 0, "label": "Container 1", "food_item_id": rice["id"],
        "open_angle": 90, "closed_angle": 0, "capacity_g": 1000, "estimated_remaining_g": 800})
    assert container.status_code == 201, container.text
    return {"device": device, "esp": esp, "container": container.json(), "rice": rice, "auth": auth}


def dispense(client, s, grams=100, key=None, **extra):
    body = {"device_id": s["device"]["id"], "container_id": s["container"]["id"], "target_weight_g": grams,
            "meal_type": "lunch", **extra}
    return client.post(f"{API}/dispenser/commands", json=body,
                       headers={**s["auth"], "Idempotency-Key": key or uuid.uuid4().hex})


def test_device_token_shown_once_and_hashed(client, auth, db):
    from app.models.device import Device
    r = client.post(f"{API}/devices", json={"name": "Test"}, headers=auth).json()
    stored = db.get(Device, uuid.UUID(r["device"]["id"]))
    assert r["device_token"] not in stored.token_hash
    listed = client.get(f"{API}/devices", headers=auth).json()
    assert "device_token" not in listed[0]


def test_device_auth_rejects_bad_token(client, setup):
    bad = FakeESP32(client, setup["device"]["id"], "dbd_wrong")
    assert bad.next().status_code == 401
    assert bad.heartbeat().status_code == 401
    assert client.get(f"{API}/devices/{setup['device']['id']}/commands/next").status_code == 401


def test_device_registration_and_online_status(client, setup):
    d = client.get(f"{API}/devices/{setup['device']['id']}", headers=setup["auth"]).json()
    assert d["is_online"] and d["is_registered"] and d["hardware_info"]["servo_count"] == 2
    assert d["containers"][0]["food"]["name"] == "White rice, raw (dry)"


def test_servo_channel_validated_against_hardware(client, setup):
    r = client.post(f"{API}/devices/{setup['device']['id']}/containers", headers=setup["auth"], json={
        "slot_number": 2, "servo_channel": 5, "label": "Container 2", "open_angle": 90, "closed_angle": 0})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_servo_channel"
    dup = client.post(f"{API}/devices/{setup['device']['id']}/containers", headers=setup["auth"], json={
        "slot_number": 2, "servo_channel": 0, "label": "Container 2", "open_angle": 90, "closed_angle": 0})
    assert dup.status_code == 409


def test_full_dispense_logs_measured_weight_not_target(client, setup):
    esp = setup["esp"]
    cmd = dispense(client, setup, 100).json()
    assert cmd["status"] == "pending"

    polled = esp.next()
    assert polled.status_code == 200
    payload = polled.json()
    assert payload["command_id"] == cmd["id"] and payload["target_weight_g"] == 100
    assert payload["servo_channel"] == 0 and payload["open_angle"] == 90 and payload["closed_angle"] == 0

    assert esp.ack(cmd["id"]).json()["already_acknowledged"] is False
    assert esp.next().status_code == 204  # acknowledged commands are never handed out again
    assert esp.progress(cmd["id"], 45.2).json()["abort"] is False

    result = esp.result(cmd["id"], dispensed=97.4).json()
    assert result["status"] == "completed" and result["meal_entry_id"]

    status = client.get(f"{API}/dispenser/commands/{cmd['id']}", headers=setup["auth"]).json()
    assert status["target_weight_g"] == 100 and status["dispensed_weight_g"] == 97.4
    events = [log["event"] for log in status["logs"]]
    assert events[:3] == ["created", "acknowledged", "progress"] and "logged_to_meals" in events

    daily = client.get(f"{API}/meals/daily", headers=setup["auth"]).json()
    lunch = daily["meals"][1]["entries"]
    assert len(lunch) == 1 and lunch[0]["quantity_g"] == 97.4 and lunch[0]["source"] == "dispenser"
    assert lunch[0]["calories"] == pytest.approx(365 * 0.974, abs=0.01)

    device = client.get(f"{API}/devices/{setup['device']['id']}", headers=setup["auth"]).json()
    assert device["containers"][0]["estimated_remaining_g"] == pytest.approx(702.6)


def test_idempotency_key_prevents_duplicate_commands(client, setup):
    first = dispense(client, setup, 50, key="press-0001-abcdef")
    second = dispense(client, setup, 50, key="press-0001-abcdef")
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_second_command_while_busy_is_rejected(client, setup):
    assert dispense(client, setup, 50).status_code == 201
    busy = dispense(client, setup, 50)
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "device_busy"


def test_retried_ack_and_result_are_idempotent(client, setup, db):
    from app.models.meal import MealEntry
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    assert esp.ack(cid).json()["already_acknowledged"] is True
    first = esp.result(cid, dispensed=99.0).json()
    retry = esp.result(cid, dispensed=99.0).json()
    assert retry["duplicate"] is True and retry["meal_entry_id"] == first["meal_entry_id"]
    assert db.query(MealEntry).count() == 1


def test_failed_dispense_is_not_logged(client, setup):
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    r = esp.result(cid, status="failed", dispensed=12.3, error_code="no_flow",
                   error_message="Weight did not increase; container may be empty.").json()
    assert r["status"] == "failed" and r["meal_entry_id"] is None
    assert client.get(f"{API}/meals/daily", headers=setup["auth"]).json()["totals"]["calories"] == 0
    # The user may explicitly log what the scale measured.
    logged = client.post(f"{API}/dispenser/commands/{cid}/log-measured", json={}, headers=setup["auth"])
    assert logged.status_code == 200 and logged.json()["meal_entry_id"]
    again = client.post(f"{API}/dispenser/commands/{cid}/log-measured", json={}, headers=setup["auth"])
    assert again.status_code == 409


def test_completed_without_measured_weight_becomes_failed(client, setup):
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    r = esp.result(cid, dispensed=0.0).json()
    assert r["status"] == "failed" and r["meal_entry_id"] is None


def test_offline_device_rejects_commands(client, setup, db):
    from app.models.device import Device
    device = db.get(Device, uuid.UUID(setup["device"]["id"]))
    device.last_heartbeat_at = utcnow() - timedelta(minutes=5)
    db.commit()
    r = dispense(client, setup, 100)
    assert r.status_code == 409 and r.json()["error"]["code"] == "device_offline"


def test_uncalibrated_scale_blocks_dispensing(client, setup):
    setup["esp"].register(calibrated=False)
    r = dispense(client, setup, 100)
    assert r.status_code == 409 and r.json()["error"]["code"] == "scale_not_calibrated"


def test_target_range_and_container_food_validated(client, setup):
    assert dispense(client, setup, 2).status_code == 422
    assert dispense(client, setup, 5000).status_code == 422
    empty = client.post(f"{API}/devices/{setup['device']['id']}/containers", headers=setup["auth"], json={
        "slot_number": 2, "servo_channel": 1, "label": "Container 2", "open_angle": 90, "closed_angle": 0}).json()
    r = client.post(f"{API}/dispenser/commands", headers={**setup["auth"], "Idempotency-Key": uuid.uuid4().hex},
                    json={"device_id": setup["device"]["id"], "container_id": empty["id"],
                          "target_weight_g": 50, "meal_type": "lunch"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "container_without_food"


def test_expired_command_is_never_delivered(client, setup, db):
    cid = dispense(client, setup, 100).json()["id"]
    cmd = db.get(DispensingCommand, uuid.UUID(cid))
    cmd.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert setup["esp"].next().status_code == 204
    status = client.get(f"{API}/dispenser/commands/{cid}", headers=setup["auth"]).json()
    assert status["status"] == "expired"
    assert setup["esp"].ack(cid).status_code == 409


def test_result_timeout_then_late_result_is_accepted(client, setup, db):
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    cmd = db.get(DispensingCommand, uuid.UUID(cid))
    cmd.acknowledged_at = utcnow() - timedelta(minutes=4)
    db.commit()
    status = client.get(f"{API}/dispenser/commands/{cid}", headers=setup["auth"]).json()
    assert status["status"] == "failed" and status["error_code"] == "result_timeout"
    late = esp.result(cid, dispensed=88.0).json()
    assert late["status"] == "completed" and late["meal_entry_id"]


def test_user_cancel_pending_and_running(client, setup):
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    r = client.post(f"{API}/dispenser/commands/{cid}/cancel", headers=setup["auth"]).json()
    assert r["status"] == "cancelled"
    assert esp.next().status_code == 204

    cid2 = dispense(client, setup, 100).json()["id"]
    esp.ack(cid2)
    r2 = client.post(f"{API}/dispenser/commands/{cid2}/cancel", headers=setup["auth"]).json()
    assert r2["status"] == "acknowledged" and r2["cancel_requested"] is True
    assert esp.progress(cid2, 20.0).json() == {"abort": True, "reason": "cancel_requested"}
    final = esp.result(cid2, status="cancelled", dispensed=21.5, error_code="cancelled").json()
    assert final["status"] == "cancelled" and final["meal_entry_id"] is None


def test_emergency_stop_aborts_and_blocks_until_reset(client, setup):
    esp = setup["esp"]
    did = setup["device"]["id"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    stop = client.post(f"{API}/devices/{did}/emergency-stop", json={"reason": "test"}, headers=setup["auth"])
    assert stop.status_code == 200
    assert esp.progress(cid, 30.0).json()["reason"] == "emergency_stop"
    assert esp.heartbeat().json()["emergency_stop_active"] is True
    esp.result(cid, status="cancelled", dispensed=31.0, error_code="emergency_stop")

    blocked = dispense(client, setup, 50)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "emergency_stop_active"
    reset = client.post(f"{API}/devices/{did}/emergency-stop/reset", headers=setup["auth"])
    assert reset.status_code == 200 and reset.json()["emergency_stop_active"] is False
    assert dispense(client, setup, 50).status_code == 201


def test_device_can_trigger_emergency_stop(client, setup):
    esp = setup["esp"]
    r = client.post(f"{API}/devices/{esp.id}/emergency-stop", json={"reason": "local"}, headers=esp.h)
    assert r.status_code == 200
    d = client.get(f"{API}/devices/{esp.id}", headers=setup["auth"]).json()
    assert d["emergency_stop_active"] is True


def test_device_reboot_mid_dispense_fails_command(client, setup):
    esp = setup["esp"]
    cid = dispense(client, setup, 100).json()["id"]
    esp.ack(cid)
    esp.register(interrupted_command_id=cid, reset_reason="brownout")
    status = client.get(f"{API}/dispenser/commands/{cid}", headers=setup["auth"]).json()
    assert status["status"] == "failed" and status["error_code"] == "device_rebooted"


def test_tare_command(client, setup):
    esp = setup["esp"]
    r = client.post(f"{API}/dispenser/commands", headers={**setup["auth"], "Idempotency-Key": uuid.uuid4().hex},
                    json={"device_id": esp.id, "command_type": "tare"})
    assert r.status_code == 201
    payload = esp.next().json()
    assert payload["type"] == "tare" and payload["target_weight_g"] is None
    esp.ack(payload["command_id"])
    res = esp.result(payload["command_id"], dispensed=0.0, final_weight_g=0.0)
    assert res.json()["status"] == "completed" and res.json()["meal_entry_id"] is None


def test_other_users_cannot_access_device_or_commands(client, setup):
    other, _ = register_user(client)
    did = setup["device"]["id"]
    assert client.get(f"{API}/devices/{did}", headers=other).status_code == 404
    assert client.post(f"{API}/devices/{did}/emergency-stop", json={}, headers=other).status_code == 404
    cid = dispense(client, setup, 50).json()["id"]
    assert client.get(f"{API}/dispenser/commands/{cid}", headers=other).status_code == 404
    hijack = client.post(f"{API}/dispenser/commands", headers={**other, "Idempotency-Key": uuid.uuid4().hex},
                         json={"device_id": did, "container_id": setup["container"]["id"],
                               "target_weight_g": 50, "meal_type": "lunch"})
    assert hijack.status_code == 404


def test_device_cannot_touch_another_devices_command(client, setup, auth):
    created = client.post(f"{API}/devices", json={"name": "Second"}, headers=auth).json()
    other_esp = FakeESP32(client, created["device"]["id"], created["device_token"])
    cid = dispense(client, setup, 50).json()["id"]
    assert other_esp.ack(cid).status_code == 404
