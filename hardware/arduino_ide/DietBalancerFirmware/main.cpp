/*
 Diet Balancer - ESP32 smart food dispenser firmware

 Core 1 (Arduino loop): HX711 sampling, dispensing state machine, OLED, serial console.
 Core 0 (net task):     Wi-Fi, registration, heartbeat, command polling, progress, results.

 The ESP32 always initiates the connection (polling), so it works behind a home router.
 First boot: it opens a "DietBalancer-XXXX" setup hotspot for Wi-Fi, finds the server by
 mDNS, then shows a 6-digit pairing code to enter in the web app. No code editing.
 See hardware/esp32/README.md for wiring, calibration and the bench test procedure.
*/
#include <Arduino.h>
#include <esp_system.h>
#include "config.h"
#include "console.h"
#include "dispenser.h"
#include "display.h"
#include "net.h"
#include "scale.h"
#include "servos.h"
#include "shared.h"
#include "storage.h"

// No secrets.h: Wi-Fi, server address and the device token are set up at runtime
// (setup hotspot + pairing code) and stored in flash.

static const char* resetReasonName() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power_on";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_DEEPSLEEP: return "deep_sleep";
    default: return "other";
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\n\nDiet Balancer dispenser firmware %s (reset: %s)\n", FIRMWARE_VERSION, resetReasonName());

  storage::begin();
  // Safety first: put every servo with a known closed angle into its closed position
  // before anything else happens. Servos with unknown angles stay unpowered.
  servos::begin();
  display::begin();
  Serial.printf("OLED: %s\n", display::ok() ? "found" : "NOT found (continuing without display)");
  scale.begin();
  Serial.printf("HX711: %s, calibrated: %s\n", scale.ready() ? "ready" : "NOT READY", scale.calibrated() ? "yes" : "NO");
  if (!scale.calibrated()) Serial.println("!! Dispensing disabled until calibrated. Type 'help'.");
  dispenser::begin();

  String interrupted = storage::inflightCommand();
  if (interrupted.length()) Serial.printf("Previous command %s was interrupted by a reset; reporting it.\n", interrupted.c_str());
  storage::setLastExecutedCommand(interrupted.length() ? interrupted : storage::lastExecutedCommand());

  net::startTask(resetReasonName(), interrupted);
  enableLoopWDT();  // reboot (and close gates on boot) if the control loop ever hangs
  Serial.println("Type 'help' for bench-test commands.");
}

void loop() {
  scale.update();

  SHARED_LOCK();
  shared.weightG = scale.grams();
  shared.scaleReady = scale.ready();
  shared.calibrated = scale.calibrated();
  bool ready = shared.commandReady;
  Command cmd = shared.command;
  if (ready) shared.commandReady = false;
  SHARED_UNLOCK();

  if (ready && !dispenser::busy()) dispenser::start(cmd);
  dispenser::tick();

  // Belt and braces: if nothing is running, no gate should stay open. Bench 'servo'
  // tests get 30 s, then everything is closed automatically.
  static unsigned long openIdleSince = 0;
  if (!dispenser::busy() && servos::anyOpen()) {
    if (!openIdleSince) openIdleSince = millis();
    if (millis() - openIdleSince > 30000) {
      servos::closeAll();
      Serial.println("Idle gate left open for 30 s; closed automatically.");
    }
  } else {
    openIdleSince = 0;
  }

  console::poll();
  display::update();
  feedLoopWDT();
  delay(2);  // yield; HX711 delivers ~10 samples/s so this costs nothing
}
