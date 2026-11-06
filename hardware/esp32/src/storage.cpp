#include "storage.h"
#include <Preferences.h>
#include <esp_random.h>
#include "config.h"

static Preferences prefs;

namespace storage {
void begin() { prefs.begin("dietbal", false); }

float calibrationFactor() {
  float stored = prefs.getFloat("cal", 0.0f);
  return stored != 0.0f ? stored : HX711_CALIBRATION_FACTOR;
}
void setCalibrationFactor(float factor) { prefs.putFloat("cal", factor); }

long scaleOffset() { return prefs.getLong("offset", 0); }
void setScaleOffset(long offset) { prefs.putLong("offset", offset); }

int closedAngle(uint8_t channel) {
  char key[8];
  snprintf(key, sizeof(key), "cl%u", channel);
  return prefs.getInt(key, -1);
}
void setClosedAngle(uint8_t channel, int angle) {
  char key[8];
  snprintf(key, sizeof(key), "cl%u", channel);
  if (prefs.getInt(key, -1) != angle) prefs.putInt(key, angle);
}

String inflightCommand() { return prefs.getString("inflight", ""); }
void setInflightCommand(const String& id) { prefs.putString("inflight", id); }
String lastExecutedCommand() { return prefs.getString("lastcmd", ""); }
void setLastExecutedCommand(const String& id) { prefs.putString("lastcmd", id); }

// Values typed into my_settings.h win; otherwise use what the setup page saved.
String wifiSsid() { return strlen(WIFI_SSID) ? String(WIFI_SSID) : prefs.getString("ssid", ""); }
String wifiPassword() { return strlen(WIFI_SSID) ? String(WIFI_PASSWORD) : prefs.getString("wpass", ""); }
void setWifi(const String& ssid, const String& password) {
  prefs.putString("ssid", ssid);
  prefs.putString("wpass", password);
}
String serverUrl() {
  if (strlen(SERVER_URL)) return String(SERVER_URL);  // my_settings.h wins
  return prefs.getString("server", "");               // `server <url>` command / setup page
}
void setServerUrl(const String& url) { prefs.putString("server", url); }
String deviceId() { return prefs.getString("devid", ""); }
String deviceToken() { return prefs.getString("devtok", ""); }
void setDeviceCredentials(const String& id, const String& token) {
  prefs.putString("devid", id);
  prefs.putString("devtok", token);
}
void clearDeviceCredentials() {
  prefs.remove("devid");
  prefs.remove("devtok");
}
String setupApPassword() {
  String p = prefs.getString("appass", "");
  if (p.length() != 8) {
    char buf[9];
    snprintf(buf, sizeof(buf), "%08lu", (unsigned long)(esp_random() % 100000000UL));
    p = buf;
    prefs.putString("appass", p);
  }
  return p;
}
void factoryReset() {
  // Keeps the scale calibration and servo closed angles: they describe the hardware.
  float cal = prefs.getFloat("cal", 0.0f);
  long offset = prefs.getLong("offset", 0);
  int cl0 = prefs.getInt("cl0", -1), cl1 = prefs.getInt("cl1", -1);
  prefs.clear();
  if (cal != 0.0f) prefs.putFloat("cal", cal);
  prefs.putLong("offset", offset);
  if (cl0 >= 0) prefs.putInt("cl0", cl0);
  if (cl1 >= 0) prefs.putInt("cl1", cl1);
}
}  // namespace storage
