// Small persistent settings in ESP32 NVS (flash).
#pragma once
#include <Arduino.h>

namespace storage {
void begin();
float calibrationFactor();               // 0 = not calibrated
void setCalibrationFactor(float factor);
long scaleOffset();
void setScaleOffset(long offset);
int closedAngle(uint8_t channel);        // -1 = unknown
void setClosedAngle(uint8_t channel, int angle);
String inflightCommand();                // command that was running when power was lost
void setInflightCommand(const String& id);
String lastExecutedCommand();            // never execute the same command twice
void setLastExecutedCommand(const String& id);

// Set at runtime (setup page / pairing). Nothing secret is compiled into the firmware.
String wifiSsid();
String wifiPassword();
void setWifi(const String& ssid, const String& password);
String serverUrl();                      // empty = find the server automatically (mDNS)
void setServerUrl(const String& url);
String deviceId();
String deviceToken();
void setDeviceCredentials(const String& id, const String& token);
void clearDeviceCredentials();
String setupApPassword();                // random 8 digits, created on first boot
void factoryReset();
}
