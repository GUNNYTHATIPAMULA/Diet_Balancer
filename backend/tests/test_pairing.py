"""Code-based pairing ("connect like AirPods"). Device side is simulated over HTTP."""
import secrets

from app.models.device import PairingSession
from tests.conftest import register_user

API = "/api/v1/devices/pairing"


def announce(client, hw="DB-3A7F1C", secret=None, **over):
    body = {"hardware_id": hw, "pairing_secret": secret or secrets.token_hex(24), "firmware_version": "1.1.0",
            "servo_count": 2, "hx711_ready": True, "oled_ready": True, "calibrated": True,
            "local_ip": "192.168.1.50", **over}
    r = client.post(f"{API}/announce", json=body)
    assert r.status_code == 200, r.text
    return r.json(), body["pairing_secret"]


def test_full_pairing_flow_without_copying_tokens(client, auth):
    first, secret = announce(client)
    assert first["status"] == "waiting" and len(first["pairing_code"]) == 6 and first["device_token"] is None

    nearby = client.get(f"{API}/nearby", headers=auth).json()  # TestClient IP "testclient" -> see next test
    claim = client.post(f"{API}/claim", headers=auth, json={"pairing_code": first["pairing_code"], "name": "Kitchen"})
    assert claim.status_code == 200, claim.text
    device = claim.json()["device"]
    assert claim.json()["reconnected"] is False and device["name"] == "Kitchen"

    # The device keeps announcing with its secret and receives its token.
    paired, _ = announce(client, secret=secret)
    assert paired["status"] == "paired" and paired["device_id"] == device["id"] and paired["device_token"]
    token = paired["device_token"]

    # The token works for the normal device API...
    hdr = {"X-Device-Id": device["id"], "X-Device-Token": token}
    reg = client.post("/api/v1/devices/register", headers=hdr, json={
        "firmware_version": "1.1.0", "servo_count": 2, "hx711_ready": True, "oled_ready": True, "calibrated": True})
    assert reg.status_code == 200
    # ...and once it has been used, the server no longer keeps a copy.
    again, _ = announce(client, secret=secret)
    assert again["status"] == "paired" and again["device_token"] is None
    assert isinstance(nearby, list)


def test_token_only_goes_to_the_device_holding_the_secret(client, auth):
    first, _ = announce(client, hw="DB-AAAA01")
    client.post(f"{API}/claim", headers=auth, json={"pairing_code": first["pairing_code"]})
    impostor, _ = announce(client, hw="DB-AAAA01")  # same hardware id, different secret
    assert impostor["status"] == "waiting" and impostor["device_token"] is None
    assert impostor["pairing_code"] != first["pairing_code"]


def test_wrong_code_is_rejected(client, auth):
    first, _ = announce(client)
    wrong = "000000" if first["pairing_code"] != "000000" else "111111"
    r = client.post(f"{API}/claim", headers=auth, json={"pairing_code": wrong})
    assert r.status_code == 404 and r.json()["error"]["code"] == "pairing_code_not_found"
    assert client.post(f"{API}/claim", headers=auth, json={"pairing_code": "12ab56"}).status_code == 422


def test_code_cannot_be_claimed_twice(client, auth):
    first, _ = announce(client)
    assert client.post(f"{API}/claim", headers=auth, json={"pairing_code": first["pairing_code"]}).status_code == 200
    other, _ = register_user(client)
    assert client.post(f"{API}/claim", headers=other, json={"pairing_code": first["pairing_code"]}).status_code == 404


def test_expired_code_is_replaced(client, auth, db):
    first, secret = announce(client)
    s = db.query(PairingSession).filter_by(pairing_code=first["pairing_code"]).one()
    from datetime import timedelta
    from app.utils.time import utcnow
    s.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post(f"{API}/claim", headers=auth, json={"pairing_code": first["pairing_code"]}).status_code == 404
    renewed, _ = announce(client, secret=secret)
    assert renewed["status"] == "waiting" and renewed["pairing_code"]
    assert client.post(f"{API}/claim", headers=auth, json={"pairing_code": renewed["pairing_code"]}).status_code == 200


def test_re_pairing_reconnects_existing_device_and_revokes_old_token(client, auth):
    first, s1 = announce(client, hw="DB-REPAIR")
    dev = client.post(f"{API}/claim", headers=auth, json={"pairing_code": first["pairing_code"]}).json()["device"]
    old_token = announce(client, secret=s1, hw="DB-REPAIR")[0]["device_token"]
    client.post(f"/api/v1/devices/{dev['id']}/containers", headers=auth, json={
        "slot_number": 1, "servo_channel": 0, "label": "Container 1", "open_angle": 70, "closed_angle": 0})

    # Device is factory-reset: it announces again with a new secret.
    second, s2 = announce(client, hw="DB-REPAIR")
    r = client.post(f"{API}/claim", headers=auth, json={"pairing_code": second["pairing_code"]}).json()
    assert r["reconnected"] is True and r["device"]["id"] == dev["id"]
    assert len(r["device"]["containers"]) == 1  # configuration kept
    new_token = announce(client, secret=s2, hw="DB-REPAIR")[0]["device_token"]
    assert new_token and new_token != old_token
    old = client.get(f"/api/v1/devices/{dev['id']}/commands/next", headers={"X-Device-Token": old_token})
    assert old.status_code == 401


def test_nearby_only_shows_same_network_and_never_the_code(client, auth):
    from app.services.pairing_service import same_network
    assert same_network("8.8.8.8", "8.8.8.8")            # both behind the same home router
    assert same_network("192.168.1.20", "127.0.0.1")     # server runs on the home network
    assert same_network("10.0.0.5", "172.17.0.1")        # e.g. Docker gateway
    assert not same_network("8.8.8.8", "1.1.1.1")        # two different homes
    assert not same_network("192.168.1.20", "8.8.8.8")
    assert not same_network("garbage", "8.8.8.8")
    announce(client, hw="DB-NEAR01")
    items = client.get(f"{API}/nearby", headers=auth).json()
    for item in items:
        assert "pairing_code" not in item


def test_announce_validates_input(client):
    r = client.post(f"{API}/announce", json={"hardware_id": "bad id!", "pairing_secret": "short",
                                            "firmware_version": "1", "servo_count": 2, "hx711_ready": True,
                                            "oled_ready": True, "calibrated": True})
    assert r.status_code == 422


def test_nearby_requires_login(client):
    assert client.get(f"{API}/nearby").status_code == 401


def test_device_can_choose_its_own_code_and_name(client, auth):
    first, _ = announce(client, hw="DB-OWNCODE", pairing_code="246810", device_name="Kitchen dispenser")
    assert first["pairing_code"] == "246810"  # shown on the OLED before the server answered
    items = client.get(f"{API}/nearby", headers=auth).json()
    mine = [i for i in items if i["hardware_id"] == "DB-OWNCODE"]
    if mine:  # visible when the test client counts as the same network
        assert mine[0]["display_name"] == "Kitchen dispenser · CODE" and mine[0]["suggested_name"] == "Kitchen dispenser"
    assert client.post(f"{API}/claim", headers=auth, json={"pairing_code": "246810"}).status_code == 200


def test_proposed_code_already_in_use_is_replaced(client):
    a, _ = announce(client, hw="DB-AAA111", pairing_code="135790")
    b, _ = announce(client, hw="DB-BBB222", pairing_code="135790")
    assert a["pairing_code"] == "135790" and b["pairing_code"] != "135790" and len(b["pairing_code"]) == 6
