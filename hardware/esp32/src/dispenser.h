// Bounded, non-blocking dispensing state machine. Runs on the control core only.
#pragma once
#include <Arduino.h>
#include "shared.h"

namespace dispenser {
void begin();
void tick();                     // call every loop iteration
bool start(const Command& cmd);  // false if refused (result is still reported)
void abort(const char* reason);  // close gates now, then measure and report as cancelled
bool busy();
float target();
float dispensedSoFar();
const char* phaseName();
const char* label();       // food name of the running command
uint8_t mealPos();
uint8_t mealTotal();
}
