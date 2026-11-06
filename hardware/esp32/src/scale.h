// HX711 load cell wrapper: non-blocking sampling, calibration and stability detection.
#pragma once
#include <Arduino.h>

class Scale {
 public:
  void begin();
  // Call every loop. Returns true when a new sample was taken.
  bool update();
  bool ready() const { return _ready; }              // chip responding recently
  bool calibrated() const { return _factor != 0.0f; }
  float grams() const { return _grams; }               // latest calibrated reading
  long raw() const { return _raw; }
  unsigned long lastSampleMs() const { return _lastSampleMs; }
  // True when the last `windowMs` of samples stay within `toleranceG`.
  bool stable(unsigned long windowMs, float toleranceG) const;
  float average(unsigned long windowMs) const;
  void tare();                                          // current raw average becomes zero
  float calibrateWithKnownWeight(float grams);          // returns new factor (0 on failure)
  void setFactor(float factor);
  float factor() const { return _factor; }

 private:
  struct Sample { unsigned long ms; float g; long raw; };
  Sample _buf[16];
  uint8_t _head = 0, _count = 0;
  long _raw = 0, _offset = 0;
  float _factor = 0, _grams = 0;
  bool _ready = false;
  unsigned long _lastSampleMs = 0;
  long rawAverage(uint8_t n) const;
};

extern Scale scale;
