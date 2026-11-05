// Wi-Fi, setup hotspot, server discovery, pairing and the device REST client. Runs as
// its own FreeRTOS task on core 0 so a slow request can never delay closing a gate.
#pragma once
#include <Arduino.h>

namespace net {
void startTask(const char* resetReason, const String& interruptedCommand);
String hardwareId();
}
