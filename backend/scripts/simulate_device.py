"""SIMULATED ESP32 dispenser, for testing the web app without hardware.

It follows the same HTTP protocol as the real firmware (register, heartbeat,
poll for commands, ack, progress, result) and fakes a load cell. Nothing here
proves that the physical dispenser works; it only exercises the software.

Usage (from the backend directory):
    python scripts/simulate_device.py
        -> pairs like the real dispenser: prints a 6-digit code; enter it in the web app
    python scripts/simulate_device.py --device-id <uuid> --token <dbd_...>
        -> skip pairing and use existing credentials
Options:
    --api http://localhost:8000/api/v1   backend URL
    --flow 12                             simulated grams per second while open
    --fail no_flow                        make every dispense fail this way (no_flow | sensor)
"""
import argparse
import random
import secrets
import time

import httpx


def pair(client: httpx.Client, base: str, hardware_id: str) -> tuple[str, str]:
    """Same pairing protocol as the firmware: announce until the owner enters the code."""
    secret = secrets.token_hex(24)
    code = f"{secrets.randbelow(1_000_000):06d}"  # chosen on the device, like the firmware
    print(f"[sim] OLED shows: Kitchen dispenser {hardware_id[-4:]}   code {code[:3]} {code[3:]}")
    shown = code
    while True:
        r = client.post(f"{base}/devices/pairing/announce", json={
            "hardware_id": hardware_id, "pairing_secret": secret, "firmware_version": "sim-1.1.0",
            "servo_count": 2, "hx711_ready": True, "oled_ready": True, "calibrated": True, "local_ip": "127.0.0.1",
            "pairing_code": shown, "device_name": "Kitchen dispenser"})
        r.raise_for_status()
        body = r.json()
        if body["status"] == "paired" and body.get("device_token"):
            print(f"[sim] paired as '{body.get('device_name')}' ({body['device_id']})")
            return body["device_id"], body["device_token"]
        if body.get("pairing_code") and body["pairing_code"] != shown:
            shown = body["pairing_code"]
            print(f"[sim] {hardware_id} waiting to be connected.")
            print(f"[sim] Pairing code (this is what the OLED shows):  {shown[:3]} {shown[3:]}")
            print("[sim] In the web app: Smart Dispenser -> Connect a dispenser -> enter the code.")
        time.sleep(body.get("poll_interval", 3))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000/api/v1")
    p.add_argument("--device-id")
    p.add_argument("--token")
    p.add_argument("--hardware-id", default="DB-SIM" + secrets.token_hex(2).upper())
    p.add_argument("--flow", type=float, default=12.0)
    p.add_argument("--fail", choices=["no_flow", "sensor"], default=None)
    args = p.parse_args()

    base = args.api.rstrip("/")
    client = httpx.Client(timeout=5)
    if not (args.device_id and args.token):
        args.device_id, args.token = pair(client, base, args.hardware_id)
    hdr = {"X-Device-Id": args.device_id, "X-Device-Token": args.token}
    scale = 0.0

    r = client.post(f"{base}/devices/register", headers=hdr, json={
        "firmware_version": "sim-1.0.0", "servo_count": 2, "hx711_ready": True, "oled_ready": True,
        "calibrated": True, "ip_address": "127.0.0.1", "wifi_rssi": -58, "reset_reason": "simulator"})
    r.raise_for_status()
    print(f"[sim] registered as '{r.json()['name']}'. Polling for commands. Ctrl+C to stop.")

    last_hb = 0.0
    while True:
        now = time.monotonic()
        if now - last_hb > 10:
            hb = client.post(f"{base}/devices/heartbeat", headers=hdr,
                             json={"state": "idle", "weight_g": round(scale, 1), "hx711_ready": True, "wifi_rssi": -58})
            last_hb = now
            if hb.json().get("emergency_stop_active"):
                print("[sim] emergency stop latched on server; staying idle")
        nxt = client.get(f"{base}/devices/{args.device_id}/commands/next", headers=hdr)
        if nxt.status_code == 204:
            time.sleep(2)
            continue
        cmd = nxt.json()
        cid = cmd["command_id"]
        ack = client.post(f"{base}/devices/{args.device_id}/commands/{cid}/ack", headers=hdr)
        if ack.status_code != 200:
            print(f"[sim] server refused command {cid}: {ack.text}")
            continue
        if cmd["type"] == "tare":
            scale = 0.0
            client.post(f"{base}/devices/{args.device_id}/commands/{cid}/result", headers=hdr,
                        json={"status": "completed", "start_weight_g": 0, "final_weight_g": 0, "dispensed_weight_g": 0})
            print("[sim] scale zeroed")
            continue

        target = cmd["target_weight_g"]
        s = cmd["settings"]
        print(f"[sim] dispensing {target} g from servo {cmd['servo_channel']} "
              f"(open {cmd['open_angle']}°, closed {cmd['closed_angle']}°)")
        start, dispensed, t0, status, err = scale, 0.0, time.monotonic(), "completed", None
        stop_at = target - s["inflight_g"]
        while dispensed < stop_at:
            time.sleep(0.5)
            if args.fail == "no_flow" and time.monotonic() - t0 > s["no_flow_timeout_ms"] / 1000:
                status, err = "failed", "no_flow"
                break
            if args.fail == "sensor" and dispensed > target * 0.4:
                status, err = "failed", "sensor_timeout"
                break
            if args.fail != "no_flow":
                rate = args.flow if target - dispensed > s["slowdown_g"] else args.flow / 3
                dispensed += rate * 0.5 * random.uniform(0.8, 1.2)
            pr = client.post(f"{base}/devices/{args.device_id}/commands/{cid}/progress", headers=hdr,
                             json={"weight_g": round(start + dispensed, 1), "phase": "dispensing"})
            if pr.json().get("abort"):
                status, err = "cancelled", pr.json().get("reason")
                break
            if (time.monotonic() - t0) * 1000 > s["max_duration_ms"]:
                status, err = "failed", "timeout"
                break
        if status == "completed":
            dispensed += random.uniform(0.6, 1.0) * s["inflight_g"]  # food still in flight lands
        time.sleep(1.0)
        scale = start + dispensed
        if status == "completed" and dispensed < target - s["tolerance_g"]:
            status, err = "failed", "under_target"
        body = {"status": status, "start_weight_g": round(start, 1), "final_weight_g": round(scale, 1),
                "dispensed_weight_g": round(dispensed, 1), "duration_ms": int((time.monotonic() - t0) * 1000),
                "error_code": err, "error_message": {"no_flow": "Weight did not increase. The container may be empty or jammed.",
                                                     "sensor_timeout": "Load cell stopped responding; gate closed.",
                                                     "under_target": "Stopped below target."}.get(err)}
        res = client.post(f"{base}/devices/{args.device_id}/commands/{cid}/result", headers=hdr, json=body)
        print(f"[sim] {status}: {dispensed:.1f} g measured -> server says {res.json().get('status')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[sim] stopped")
