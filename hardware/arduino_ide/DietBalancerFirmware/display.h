#pragma once
#include <Arduino.h>

namespace display {
bool begin();          // false if the OLED does not answer on I2C
bool ok();
void update(bool force = false);
void message(const char* line1, const char* line2 = nullptr);
void testPattern();
}
