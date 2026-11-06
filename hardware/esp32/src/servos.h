// Servo control with safe defaults: a servo is only driven once its closed angle is known.
#pragma once
#include <Arduino.h>

namespace servos {
void begin();                                 // closes every servo whose closed angle is saved
void setClosedAngle(uint8_t channel, int angle);  // from server config; closes it immediately if idle
bool known(uint8_t channel);
void open(uint8_t channel, int angle);
void close(uint8_t channel);
void closeAll();
bool anyOpen();
void write(uint8_t channel, int angle);       // raw positioning for bench tests
}
