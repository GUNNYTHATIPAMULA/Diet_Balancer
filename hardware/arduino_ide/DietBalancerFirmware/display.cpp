#include "display.h"
#include <U8g2lib.h>
#include <Wire.h>
#include "config.h"
#include "dispenser.h"
#include "scale.h"
#include "shared.h"
#include "storage.h"

static U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, OLED_SCL_PIN, OLED_SDA_PIN);
static bool present = false;
static unsigned long lastDraw = 0;

namespace display {
bool begin() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  Wire.beginTransmission(OLED_I2C_ADDR);
  present = Wire.endTransmission() == 0;
  if (!present) return false;
  oled.setI2CAddress(OLED_I2C_ADDR << 1);
  oled.setBusClock(400000);
  oled.begin();
  message("Diet Balancer", "Starting...");
  return true;
}

bool ok() { return present; }

void message(const char* line1, const char* line2) {
  if (!present) return;
  oled.clearBuffer();
  oled.setFont(u8g2_font_7x14B_tr);
  oled.drawStr(0, 16, line1);
  if (line2) {
    oled.setFont(u8g2_font_6x10_tr);
    oled.drawStr(0, 36, line2);
  }
  oled.sendBuffer();
}

void update(bool force) {
  if (!present) return;
  unsigned long now = millis();
  // While a gate is open, redraw less often so the control loop stays responsive.
  unsigned long interval = dispenser::busy() ? 500 : DISPLAY_INTERVAL_MS;
  if (!force && now - lastDraw < interval) return;
  lastDraw = now;

  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();

  char line[48];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x10_tr);
  // Status bar
  oled.drawStr(0, 9, s.wifiOk ? s.ip : (s.mode == NetMode::WifiSetup ? "Diet Balancer" : "WiFi: connecting"));
  oled.drawStr(98, 9, s.authFailed ? "AUTH" : (s.serverOk ? "API" : "---"));
  oled.drawHLine(0, 12, 128);

  if (s.localEstop || s.serverEstop) {
    oled.setFont(u8g2_font_7x14B_tr);
    oled.drawStr(0, 32, "EMERGENCY STOP");
    oled.setFont(u8g2_font_6x10_tr);
    oled.drawStr(0, 48, "Gates closed.");
    oled.drawStr(0, 60, "Reset from web app");
  } else if (dispenser::busy()) {
    float target = dispenser::target();
    float got = dispenser::dispensedSoFar();
    snprintf(line, sizeof(line), "%s %.0fg", dispenser::phaseName(), target);
    oled.drawStr(0, 24, line);
    oled.setFont(u8g2_font_logisoso16_tr);
    snprintf(line, sizeof(line), "%.1f g", got);
    oled.drawStr(0, 46, line);
    int w = target > 0 ? (int)constrain(got / target * 124.0f, 0.0f, 124.0f) : 0;
    oled.drawFrame(0, 52, 128, 10);
    oled.drawBox(2, 54, w, 6);
  } else if (s.mode == NetMode::WifiSetup) {
    oled.setFont(u8g2_font_7x14B_tr);
    oled.drawStr(0, 26, "Wi-Fi setup");
    oled.setFont(u8g2_font_6x10_tr);
    snprintf(line, sizeof(line), "Join: %s", s.apSsid);
    oled.drawStr(0, 40, line);
    snprintf(line, sizeof(line), "Password: %s", s.apPassword);
    oled.drawStr(0, 51, line);
    oled.drawStr(0, 62, "Then open 192.168.4.1");
  } else if (s.mode == NetMode::ServerNotFound) {
    oled.drawStr(0, 24, "Server not found");
    snprintf(line, sizeof(line), "Join: %s", s.apSsid);
    oled.drawStr(0, 37, line);
    snprintf(line, sizeof(line), "Password: %s", s.apPassword);
    oled.drawStr(0, 49, line);
    oled.drawStr(0, 61, "Open 192.168.4.1");
  } else if (!s.wifiOk) {
    oled.drawStr(0, 30, "Connecting to Wi-Fi...");
    oled.drawStr(0, 44, storage::wifiSsid().c_str());
    oled.setFont(u8g2_font_5x8_tr);
    oled.drawStr(0, 62, "Check my_settings.h");
  } else if (!s.paired && s.pairingCode[0]) {
    // Pairing screen: shown as soon as Wi-Fi is up, with the code chosen on the device.
    oled.setFont(u8g2_font_5x8_tr);
    snprintf(line, sizeof(line), "%s %s", DEVICE_NAME, s.hardwareId[0] ? s.hardwareId + strlen(s.hardwareId) - 4 : "");
    oled.drawStr(0, 21, line);
    oled.setFont(u8g2_font_logisoso22_tn);
    snprintf(line, sizeof(line), "%.3s %.3s", s.pairingCode, s.pairingCode + 3);
    oled.drawStr((128 - oled.getStrWidth(line)) / 2, 49, line);
    oled.setFont(u8g2_font_5x8_tr);
    const char* hint = s.serverOk ? "Web app > Connect > enter code"
                     : s.mode == NetMode::FindingServer ? "Looking for the server..."
                     : "Can't reach server: nettest";
    oled.drawStr(0, 62, hint);
  } else {
    if (!s.scaleReady) {
      oled.drawStr(0, 28, "Scale not responding");
    } else if (!s.calibrated) {
      oled.drawStr(0, 28, "Scale NOT calibrated");
      oled.drawStr(0, 40, "Serial: cal <grams>");
    } else {
      oled.setFont(u8g2_font_logisoso22_tr);
      snprintf(line, sizeof(line), "%.1f g", s.weightG);
      oled.drawStr(0, 42, line);
      oled.setFont(u8g2_font_6x10_tr);
    }
    oled.drawStr(0, 62, s.lastError[0] ? s.lastError
                        : s.registered ? "Ready"
                        : (s.mode == NetMode::Pairing && !s.serverOk) ? "Can't reach server" : "Connecting to server");
  }
  oled.sendBuffer();
}

void testPattern() {
  if (!present) return;
  oled.clearBuffer();
  oled.drawFrame(0, 0, 128, 64);
  oled.drawLine(0, 0, 127, 63);
  oled.drawLine(0, 63, 127, 0);
  oled.setFont(u8g2_font_6x10_tr);
  oled.drawStr(30, 36, "OLED TEST OK?");
  oled.sendBuffer();
}
}  // namespace display
