#include "console.h"
#include <Arduino.h>
#include <WiFi.h>
#include "config.h"
#include "dispenser.h"
#include "display.h"
#include "scale.h"
#include "servos.h"
#include "shared.h"
#include "storage.h"

static String line;
static unsigned long lastCharAt = 0;

static void help() {
  Serial.println(F(
      "\nCommands:\n"
      "  status               device, Wi-Fi, scale and server status\n"
      "  weigh                print 10 readings (raw + grams)\n"
      "  tare                 zero the scale with the current load\n"
      "  cal <grams>          calibrate: tare empty, then place a known weight and run this\n"
      "  setcal <factor>      set a known calibration factor (counts per gram)\n"
      "  servo <ch> <angle>   move a servo (bench test, only while idle)\n"
      "  close                close every servo with a known closed angle\n"
      "  oled                 draw a test pattern\n"
      "  stop                 local emergency stop (closes all gates, reported to server)\n"
      "  nettest              step-by-step check of the connection to the server\n"
      "  unpair               disconnect from the account and show a new pairing code\n"
      "  wifi-reset           forget Wi-Fi and reopen the setup hotspot\n"
      "  server <url>|auto    set the server address, or find it automatically (mDNS)\n"
      "  factory-reset        forget Wi-Fi, server and pairing (keeps calibration)\n"
      "  reset                clear the LOCAL emergency stop (server stop is reset from the web app)\n"
      "  reboot               restart the ESP32"));
}

static void status() {
  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();
  static const char* modes[] = {"starting", "wifi setup", "connecting wifi", "finding server", "server not found", "pairing", "ready"};
  Serial.printf("Device name: %s | Wi-Fi from: %s\n", DEVICE_NAME, strlen(WIFI_SSID) ? "my_settings.h" : "setup page");
  Serial.printf("Firmware %s | hardware %s | mode: %s | paired: %s\n", FIRMWARE_VERSION, s.hardwareId,
                modes[(int)s.mode], storage::deviceToken().length() ? "yes" : "no");
  if (s.mode == NetMode::Pairing) Serial.printf("Pairing code: %s\n", s.pairingCode);
  Serial.printf("WiFi '%s' %s %s RSSI %d | server %s (%s) | registered %s\n", storage::wifiSsid().c_str(),
                s.wifiOk ? "up" : "down", s.ip, WiFi.RSSI(), s.serverOk ? "ok" : "unreachable",
                storage::serverUrl().length() ? storage::serverUrl().c_str() : "auto", s.registered ? "yes" : "no");
  Serial.printf("Setup hotspot: %s / %s\n", s.apSsid, s.apPassword);
  Serial.printf("Scale ready %s | calibrated %s (factor %.4f) | weight %.1f g | raw %ld\n", scale.ready() ? "yes" : "NO",
                scale.calibrated() ? "yes" : "NO", scale.factor(), scale.grams(), scale.raw());
  Serial.printf("Dispenser %s | estop local %s server %s | OLED %s | last error: %s\n", dispenser::phaseName(),
                s.localEstop ? "ON" : "off", s.serverEstop ? "ON" : "off", display::ok() ? "ok" : "missing",
                s.lastError[0] ? s.lastError : "none");
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++)
    Serial.printf("Servo %u on GPIO %u: closed angle %d\n", ch, SERVO_PINS[ch], storage::closedAngle(ch));
}

static void handle(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;
  int sp = cmd.indexOf(' ');
  String word = sp < 0 ? cmd : cmd.substring(0, sp);
  String args = sp < 0 ? "" : cmd.substring(sp + 1);
  word.toLowerCase();

  if (word == "help") return help();
  if (word == "status") return status();
  if (word == "stop") {
    dispenser::abort("Local emergency stop");
    servos::closeAll();
    SHARED_LOCK();
    shared.localEstop = true;
    shared.estopToReport = true;
    SHARED_UNLOCK();
    Serial.println("EMERGENCY STOP: gates closed, new commands refused.");
    return;
  }
  if (word == "reset") {
    SHARED_LOCK();
    shared.localEstop = false;
    bool server = shared.serverEstop;
    SHARED_UNLOCK();
    Serial.println(server ? "Local stop cleared. Server stop still active; reset it in the web app."
                          : "Local stop cleared.");
    return;
  }
  if (word == "nettest") {
    SHARED_LOCK();
    shared.netTestRequested = true;
    SHARED_UNLOCK();
    Serial.println("Testing the connection to the server...");
    return;
  }
  if (word == "unpair") {
    SHARED_LOCK();
    shared.unpairRequested = true;
    SHARED_UNLOCK();
    Serial.println("Disconnecting from the account; a new pairing code will appear.");
    return;
  }
  if (word == "wifi-reset" && strlen(WIFI_SSID)) {
    Serial.println("Wi-Fi is set in my_settings.h. Change it there (or set it to \"\") and upload again.");
    return;
  }
  if (word == "wifi-reset") {
    SHARED_LOCK();
    shared.forgetWifiRequested = true;
    SHARED_UNLOCK();
    return;
  }
  if (word == "server" && strlen(SERVER_URL)) {
    Serial.printf("Server address is set in my_settings.h (%s). Change it there and upload again.\n", SERVER_URL);
    return;
  }
  if (word == "server") {
    args.trim();
    if (args == "auto" || !args.length()) storage::setServerUrl("");
    else storage::setServerUrl(args.startsWith("http") ? args : "http://" + args);
    Serial.println("Saved. Restarting...");
    delay(300);
    ESP.restart();
  }
  if (word == "factory-reset") {
    servos::closeAll();
    storage::factoryReset();
    Serial.println("Wi-Fi, server and pairing forgotten (calibration kept). Restarting...");
    delay(300);
    ESP.restart();
  }
  if (word == "reboot") { servos::closeAll(); delay(300); ESP.restart(); }
  if (word == "oled") { display::testPattern(); Serial.println(display::ok() ? "Pattern drawn. Check the screen." : "OLED not detected on I2C."); return; }

  if (dispenser::busy()) { Serial.println("Busy dispensing; try again when idle (or 'stop')."); return; }

  if (word == "weigh") {
    for (int i = 0; i < 10; i++) {
      unsigned long t = millis();
      while (!scale.update() && millis() - t < 500) delay(5);
      Serial.printf("raw %ld  ->  %.2f g%s\n", scale.raw(), scale.grams(), scale.ready() ? "" : "  (HX711 NOT READY)");
    }
  } else if (word == "tare") {
    scale.tare();
    Serial.println("Scale zeroed. Wait a second before weighing.");
  } else if (word == "cal") {
    float g = args.toFloat();
    float f = scale.calibrateWithKnownWeight(g);
    if (f == 0) Serial.println("Calibration failed. Run 'tare' with the scale empty, place a known weight, wait 2 s, then 'cal <grams>'.");
    else Serial.printf("Calibration factor %.4f saved. Put this in config.h (HX711_CALIBRATION_FACTOR) to keep it after a flash erase.\n", f);
  } else if (word == "setcal") {
    float f = args.toFloat();
    if (f == 0) { Serial.println("Usage: setcal <non-zero factor>"); return; }
    scale.setFactor(f);
    Serial.printf("Calibration factor set to %.4f\n", f);
  } else if (word == "servo") {
    int ch = args.toInt();
    int sp2 = args.indexOf(' ');
    if (sp2 < 0 || ch < 0 || ch >= SERVO_COUNT) { Serial.printf("Usage: servo <0-%d> <0-180>\n", SERVO_COUNT - 1); return; }
    bool estop;
    SHARED_LOCK();
    estop = shared.localEstop || shared.serverEstop;
    SHARED_UNLOCK();
    if (estop) { Serial.println("Emergency stop is active."); return; }
    int angle = constrain(args.substring(sp2 + 1).toInt(), 0, 180);
    servos::write(ch, angle);
    Serial.printf("Servo %d (GPIO %u) -> %d deg. Use 'close' when done.\n", ch, SERVO_PINS[ch], angle);
  } else if (word == "close") {
    servos::closeAll();
    Serial.println("All servos with a known closed angle were closed.");
  } else {
    Serial.println("Unknown command. Type 'help'.");
  }
}

namespace console {
void poll() {
  while (Serial.available()) {
    char c = Serial.read();
    lastCharAt = millis();
    if (c == '\n' || c == '\r') {
      handle(line);
      line = "";
    } else if (line.length() < 64) {
      line += c;
    }
  }
  // Works even if the Serial Monitor is set to "No line ending": run the command
  // once nothing more has arrived for 300 ms.
  if (line.length() && millis() - lastCharAt > 300) {
    handle(line);
    line = "";
  }
}
}  // namespace console
