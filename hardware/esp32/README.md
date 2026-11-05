# ESP32 smart dispenser firmware

Status: **compiles with zero warnings** on ESP32 Arduino cores 3.0.7 and 2.0.17 (2.0.17 is
the core used by `platform = espressif32@6.9.0`), and the dispensing state machine passes simulated host
tests. **It has not been run on your hardware yet.** Treat every number below as a
starting point until you've completed the bench procedure.

## Wiring (from the verified prototype)

| Part | ESP32 pin | Notes |
|---|---|---|
| Servo channel 0 | GPIO 13 | "servo 0" in the web app |
| Servo channel 1 | GPIO 14 | "servo 1" in the web app |
| HX711 DT | GPIO 32 | |
| HX711 SCK | GPIO 33 | |
| OLED SDA | GPIO 21 | SH1106 128×64, I²C 0x3C |
| OLED SCL | GPIO 22 | |

Power the servos from a separate 5 V supply with a common ground. Servos drawing current
from the ESP32's 5 V pin cause brownout resets, which the firmware reports as `brownout`.

Which servo opens which container, and the open/closed angles, are **configured in the web
app** (Smart Dispenser → Add container). Nothing about the mechanism is hard-coded.

## How it works

* **Core 1 (Arduino `loop`)** samples the HX711, runs the dispensing state machine,
  draws the OLED and reads the serial console. It never touches the network.
* **Core 0 (network task)** handles Wi-Fi, registration, heartbeats every 10 s, polling
  for commands every 2 s, progress every 1 s, and result delivery with retries.
  A slow HTTP request therefore cannot delay closing a gate.
* The ESP32 always calls the backend (`GET /devices/{id}/commands/next`). The backend never
  needs to reach the ESP32, so it works behind a home router.

### Safety behaviour

| Situation | What the firmware does |
|---|---|
| Boot / reset | Before anything else, every servo whose closed angle is known (saved in flash) is driven closed. Servos with unknown angles are left unpowered rather than guessed. |
| Scale not calibrated | Refuses every dispense (`not_calibrated`). |
| HX711 gives no sample for 600 ms | Closes all gates immediately, reports `sensor_timeout`, claims **no** weight. |
| Weight jumps >300 g in one sample | Closes, reports `sensor_implausible`, claims no weight. |
| Weight drops 50 g below the start | Closes, reports `bowl_removed`. |
| Gate open but weight not rising for `no_flow_timeout` | Closes, measures, reports `no_flow` (empty or jammed container). |
| Total time > `max_duration` (hard cap 120 s whatever the server sends) | Closes, measures, reports `timeout`. |
| Cancel or emergency stop from the web app | Delivered via the progress/heartbeat reply; closes, measures, reports `cancelled`. |
| Serial `stop` | Local emergency stop, also reported to the server. |
| Dispenser removed from the account | Three rejected requests, then it forgets its credentials and shows a pairing code. |
| Wi-Fi or backend lost mid-dispense | Dispensing continues safely to its own limits using the local load cell; the result is retried until delivered. |
| Power loss / crash mid-dispense | The running command id is in flash. On the next boot it is reported as interrupted, and the server marks it failed (nothing is logged). |
| Same command delivered twice | The last executed id is stored in flash; it never runs twice. |
| Control loop hangs | The loop watchdog reboots the board, which closes the gates on boot. |
| A bench `servo` test leaves a gate open | Closed automatically after 30 s idle. |

**Hardware limitation to design around:** when the ESP32 resets, servo PWM stops for
about a second until `setup()` closes the gates. A hobby servo without a signal stays
where it was. If a gate can spill in that time, make the mechanism gravity- or
spring-closed so it fails closed.

### Dispensing strategy

1. **Prepare:** wait for a stable reading (bounded) and record the start weight.
2. **Flow:** open until `target − slowdown_g`.
3. **Pulse:** short open pulses (`pulse_open_ms`) with settle pauses (`pulse_settle_ms`).
   Stop once within `tolerance_g / 2` of the target; also close early by `inflight_g`
   while food is still falling.
4. **Final settle:** wait for a stable reading and report `final − start` as the measured
   amount. **Completed** only if it's within `tolerance_g` of the target; otherwise
   `under_target`.

All of these values are editable in the web app (Smart Dispenser → Dispensing strategy),
and the firmware clamps them to its own limits.

## Setup: flash once, then connect from your phone (no code editing)

Nothing device-specific is compiled into the firmware: there's no `secrets.h`. Wi-Fi,
the server address and the device's credentials are set up at runtime and stored in the
ESP32's flash. The scale calibration (`-191.873` per gram, from your test sketch) is
already in `include/config.h`.

### 1. Flash the firmware (once)
**Arduino IDE 2.x:** open `hardware/arduino_ide/DietBalancerFirmware/DietBalancerFirmware.ino`.
It compiles on the "esp32 by Espressif" board package 3.0.7 and 2.0.17. Install these
libraries: ArduinoJson 7.x, ESP32Servo, HX711 (Bogdan Necula), U8g2. Select
**ESP32 Dev Module**, then click Upload.

**PlatformIO**, run in `hardware/esp32/`: `pio run -t upload`, then `pio device monitor`.

### 2. Wi-Fi: the setup hotspot
On first boot the OLED shows **Wi-Fi setup**, a hotspot name (`DietBalancer-XXXX`) and an
8-digit password. On your phone:
1. Join that Wi-Fi network using the password on the screen.
2. A setup page opens automatically (or open `http://192.168.4.1`).
3. Choose your home Wi-Fi from the list (2.4 GHz only) and enter its password.
4. Tap **Save and connect**. The dispenser restarts and joins your Wi-Fi.

If it can't join your Wi-Fi for 60 s (wrong password, router changed), the setup
hotspot comes back by itself.

### 3. Server: found automatically
The backend announces itself on your network (mDNS, `_dietbalancer._tcp`), and the
dispenser finds it without you typing an address. If it can't (some routers block mDNS,
or you're using Docker's default network), the OLED shows **Server not found** and
reopens the setup hotspot. Type the address there instead, e.g.
`http://192.168.1.20:8000/api/v1`.

### 4. Pairing: like connecting AirPods, with a code
The OLED shows **Connect in the web app** and a 6-digit code (e.g. `482 913`). In the
web app go to **Smart Dispenser → Connect a dispenser**. The dispenser appears under
"Found nearby". Tap **Connect** and type the code from the screen. Within a few seconds
the web app shows **Online and ready**.

* **Why a code, not one tap:** anyone on the same network would see the dispenser in the
  list. The code proves you're standing next to it (the same idea as Bluetooth pairing
  or a TV showing a code).
* **Security of the credentials:** the device's credentials are created by the server
  and handed only to the dispenser that holds a random secret it generated itself.
  The server deletes its copy once the dispenser has used them.
* **Re-pairing a dispenser you already own** reconnects the same entry and keeps its
  containers and history.
* **Removing the dispenser** in the web app makes it return to showing a pairing code
  automatically (after 3 rejected requests). Serial `unpair` does the same immediately.

### Resetting
| Serial command | Effect |
|---|---|
| `unpair` | Disconnect from the account; show a new pairing code |
| `wifi-reset` | Forget Wi-Fi; reopen the setup hotspot |
| `server <url>` / `server auto` | Set the server address, or go back to automatic search |
| `factory-reset` | Forget Wi-Fi, server and pairing (keeps calibration and servo angles) |

### Calibration
`include/config.h` uses **-191.873 counts per gram**. That's your verified test-sketch
factor `-191873.0`, converted from kilograms to grams (your sketch's `get_units()`
returned kg). The scale tares itself at boot, as in your sketch, so keep the platform
empty (or with only the empty bowl) while it starts. To re-calibrate later, use
`cal <grams>`.

## Bench test procedure

Run these in order with the serial monitor open (115200 baud, newline line ending).
**Only tick a box after you've seen it work on the real hardware.**
Record observations next to each step; they're the evidence that the hardware works.

**A. Boot and OLED**
- [ ] Serial prints `HX711: ready`, `OLED: found`.
- [ ] `oled` draws a crossed frame with "OLED TEST OK?".
- [ ] `status` shows both servos and their closed angles (`-1` = unknown until configured).

**B. HX711 reading and calibration**
- [ ] Empty scale: `tare`, then `weigh` reads within ±1 g of 0.
- [ ] Place a known weight (e.g. 200 g), wait 2 s, run `cal 200`. Note the factor and put it in `config.h`.
- [ ] `weigh` now shows the known weight within ±1 g. Repeat with a second, different weight.
- [ ] Leave the weight for 2 minutes: drift under 1 g.

**C. Servo movement** (container empty, hands clear)
- [ ] `servo 0 0`, `servo 0 90`, and so on: find the real **closed** and **open** angles for each gate. Enter them in the web app container settings.
- [ ] `close` returns every gate to its closed angle.
- [ ] Leave a gate open via `servo`: it closes automatically after 30 s.

**D. Wi-Fi setup and connectivity**
- [ ] First boot: the OLED shows the setup hotspot and password; your phone joins it and the setup page opens.
- [ ] After saving, serial shows `[wifi] connected to <your network>`; the OLED status bar shows the IP.
- [ ] Turn the router off and on: the ESP32 reconnects without a reboot.
- [ ] `wifi-reset`, then enter a wrong password on the setup page: the hotspot reappears within about 60 s.

**E. Server discovery, pairing and backend communication**
- [ ] Serial shows `[mdns] found Diet Balancer server at http://...` (or use `server <url>` if your network blocks mDNS).
- [ ] The OLED shows a 6-digit code; the web app lists the dispenser under "Found nearby".
- [ ] A wrong code is rejected; the right code shows **Online and ready**, and serial shows `[api] registered with the server`.
- [ ] The web app shows firmware, IP, RSSI and "Ready, calibrated"; the weight follows the scale within about 10 s.
- [ ] Remove the dispenser in the web app: within about 30 s the OLED shows a new pairing code. Pair it again.

**F. First real dispense** (dry food, small target)
- [ ] Web app: dispense **20 g**. The OLED shows progress, the gate closes, and the web page shows requested vs measured.
- [ ] Weigh the bowl on a separate kitchen scale: it agrees with "measured" within ±2 g.
- [ ] Repeat with 50 g and 100 g. Note the overshoot each time and tune `inflight_g`.

**G. Dispensing timeout:** set `max_duration_ms` to 5000 in the web app, then dispense 300 g.
- [ ] The gate closes after about 5 s; the result is **failed: timeout** with the measured weight; nothing is added to the food log.

**H. Empty container (no flow):** empty the container, then dispense 50 g.
- [ ] Closes after `no_flow_timeout_ms`; result **failed: no_flow**.

**I. Sensor failure:** start a 200 g dispense, then unplug the HX711 DT wire.
- [ ] The gate closes within about 1 s; result **failed: sensor_timeout**; no weight claimed.

**J. Emergency stop**
- [ ] During a 200 g dispense, press **Emergency stop** in the web app: the gate closes within about 1–2 s; result **cancelled** with the measured amount.
- [ ] The OLED shows EMERGENCY STOP; new dispenses are refused until you reset it in the web app.
- [ ] Serial `stop` during a dispense does the same and appears in the web app's device events.

**K. Power loss:** start a 200 g dispense and pull the power.
- [ ] On reboot the gates close, and the web app shows the request as **failed: device_rebooted**.

## Host logic tests (no hardware needed)

These run the real `src/dispenser.cpp` against a **simulated** load cell and gate. They
cover normal and small dispenses, empty containers, sensor loss, emergency stop, timeout,
implausible readings and server-value clamping. They check the logic only, not your
mechanism. From `hardware/esp32/`:
```bash
g++ -std=c++17 -Wall -I test/host -I include -o dispenser_test \
    test/host/dispenser_test.cpp src/dispenser.cpp src/shared.cpp && ./dispenser_test
```

## Serial commands
`help`, `status`, `weigh`, `tare`, `cal <grams>`, `setcal <factor>`, `servo <ch> <angle>`,
`close`, `oled`, `stop`, `reset`, `unpair`, `wifi-reset`, `server <url>|auto`,
`factory-reset`, `reboot`.
