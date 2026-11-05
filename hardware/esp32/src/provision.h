// Wi-Fi setup hotspot with a captive setup page (no code editing needed).
#pragma once
#include <Arduino.h>

namespace provision {
void start(const String& apSsid, const String& apPassword);  // open hotspot + page
void stop();
bool running();
void loop();               // call often from the network task
bool saveRequested();      // the page saved new settings; caller should reboot
}
