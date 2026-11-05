#include "scale.h"
#include <HX711.h>
#include "config.h"
#include "storage.h"

Scale scale;
static HX711 hx;

void Scale::begin() {
  hx.begin(HX711_DT_PIN, HX711_SCK_PIN);
  _factor = storage::calibrationFactor();
  _offset = storage::scaleOffset();
  // Wait (bounded, 2 s like the original test sketch) for the first conversion.
  unsigned long t0 = millis();
  while (millis() - t0 < 2000) {
    if (update()) break;
    delay(10);
  }
#if TARE_ON_BOOT
  if (_ready) {
    // Same procedure as the verified test sketch: let it settle ~1.5 s, then zero.
    Serial.println("Keep the scale empty (or only the empty bowl): taring...");
    unsigned long s0 = millis();
    while (millis() - s0 < 1500) {
      update();
      delay(10);
    }
    if (_count >= 5) {
      tare();
      unsigned long r0 = millis();  // refill the sample buffer relative to the new zero
      while (millis() - r0 < 300) {
        update();
        delay(10);
      }
      Serial.println("Tare complete.");
    }
  }
#endif
}

bool Scale::update() {
  unsigned long now = millis();
  if (!hx.is_ready()) {
    if (_ready && now - _lastSampleMs > SENSOR_TIMEOUT_MS) _ready = false;
    return false;
  }
  long r = hx.read();  // returns immediately because the chip is ready
  if (HX711_INVERT) r = -r;
  _raw = r;
  _grams = _factor != 0.0f ? (float)(r - _offset) / _factor : 0.0f;
  _buf[_head] = {now, _grams, r};
  _head = (_head + 1) % STABILITY_SAMPLES;
  if (_count < STABILITY_SAMPLES) _count++;
  _lastSampleMs = now;
  _ready = true;
  return true;
}

bool Scale::stable(unsigned long windowMs, float toleranceG) const {
  if (!_ready || _count < 3) return false;
  unsigned long now = millis();
  float lo = 1e9, hi = -1e9;
  uint8_t used = 0;
  unsigned long oldest = now;
  for (uint8_t i = 0; i < _count; i++) {
    const Sample& s = _buf[(_head + STABILITY_SAMPLES - 1 - i) % STABILITY_SAMPLES];
    if (now - s.ms > windowMs) break;
    lo = min(lo, s.g);
    hi = max(hi, s.g);
    oldest = s.ms;
    used++;
  }
  // Need samples that actually cover most of the window.
  return used >= 3 && (now - oldest) >= windowMs * 3 / 4 && (hi - lo) <= toleranceG;
}

float Scale::average(unsigned long windowMs) const {
  unsigned long now = millis();
  float sum = 0;
  uint8_t used = 0;
  for (uint8_t i = 0; i < _count; i++) {
    const Sample& s = _buf[(_head + STABILITY_SAMPLES - 1 - i) % STABILITY_SAMPLES];
    if (now - s.ms > windowMs) break;
    sum += s.g;
    used++;
  }
  return used ? sum / used : _grams;
}

long Scale::rawAverage(uint8_t n) const {
  long long sum = 0;
  uint8_t used = 0;
  for (uint8_t i = 0; i < _count && used < n; i++, used++)
    sum += _buf[(_head + STABILITY_SAMPLES - 1 - i) % STABILITY_SAMPLES].raw;
  return used ? (long)(sum / used) : _raw;
}

void Scale::tare() {
  _offset = rawAverage(10);
  storage::setScaleOffset(_offset);
  _count = 0;  // old samples were relative to the old zero
}

float Scale::calibrateWithKnownWeight(float grams) {
  if (grams <= 0 || _count < 5) return 0;
  long delta = rawAverage(10) - _offset;
  if (labs(delta) < 100) return 0;  // nothing measurable on the scale
  float f = (float)delta / grams;
  setFactor(f);
  return f;
}

void Scale::setFactor(float factor) {
  _factor = factor;
  storage::setCalibrationFactor(factor);
  _count = 0;
}
