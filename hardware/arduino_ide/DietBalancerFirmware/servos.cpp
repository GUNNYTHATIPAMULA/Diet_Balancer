#include "servos.h"
#include <ESP32Servo.h>
#include "config.h"
#include "storage.h"

static Servo s[SERVO_COUNT];
static int closedAngles[SERVO_COUNT];
static bool isOpen[SERVO_COUNT];

static void attach(uint8_t ch) {
  if (!s[ch].attached()) s[ch].attach(SERVO_PINS[ch], 500, 2400);
}

namespace servos {
void begin() {
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++) {
    s[ch].setPeriodHertz(50);
    closedAngles[ch] = storage::closedAngle(ch);
    isOpen[ch] = false;
    // Unknown closed position -> leave the servo unpowered rather than guess an angle.
    if (closedAngles[ch] >= 0) {
      attach(ch);
      s[ch].write(closedAngles[ch]);
    }
  }
}

void setClosedAngle(uint8_t ch, int angle) {
  if (ch >= SERVO_COUNT) return;
  angle = constrain(angle, 0, 180);
  closedAngles[ch] = angle;
  storage::setClosedAngle(ch, angle);
  if (!isOpen[ch]) {
    attach(ch);
    s[ch].write(angle);
  }
}

bool known(uint8_t ch) { return ch < SERVO_COUNT && closedAngles[ch] >= 0; }

void open(uint8_t ch, int angle) {
  if (!known(ch)) return;  // never open a gate we can't close again
  attach(ch);
  s[ch].write(constrain(angle, 0, 180));
  isOpen[ch] = true;
}

void close(uint8_t ch) {
  if (ch >= SERVO_COUNT) return;
  if (closedAngles[ch] >= 0) {
    attach(ch);
    s[ch].write(closedAngles[ch]);
  }
  isOpen[ch] = false;
}

void closeAll() {
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++) close(ch);
}

bool anyOpen() {
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++)
    if (isOpen[ch]) return true;
  return false;
}

void write(uint8_t ch, int angle) {
  if (ch >= SERVO_COUNT) return;
  attach(ch);
  s[ch].write(constrain(angle, 0, 180));
  isOpen[ch] = closedAngles[ch] < 0 || angle != closedAngles[ch];
}
}  // namespace servos
