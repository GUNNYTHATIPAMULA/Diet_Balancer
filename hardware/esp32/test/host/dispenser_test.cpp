// Host-side logic test for the dispensing state machine (SIMULATED physics, not hardware).
// Build & run: see hardware/esp32/README.md ("Host logic tests").
#define private public
#include "../../src/scale.h"
#undef private
#include "../../src/dispenser.h"
#include "../../src/servos.h"
#include "../../src/storage.h"
#include <deque>

unsigned long fakeMillis = 0;
FakeSerial Serial;
Scale scale;

// ---- fake hardware ------------------------------------------------------------
static bool gate = false;
static bool sensorDead = false;
static float flowGps = 20;       // grams per second while the gate is open
static float bowl = 0;           // food actually resting in the bowl
static std::deque<std::pair<unsigned long, float>> falling;  // food in the air, lands after 300 ms
static float jumpAt = -1;

namespace servos {
void begin() {}
void setClosedAngle(uint8_t, int) {}
bool known(uint8_t) { return true; }
void open(uint8_t, int) { gate = true; }
void close(uint8_t) { gate = false; }
void closeAll() { gate = false; }
bool anyOpen() { return gate; }
void write(uint8_t, int) {}
}
namespace storage {
void begin() {}
float calibrationFactor() { return 1; }
void setCalibrationFactor(float) {}
long scaleOffset() { return 0; }
void setScaleOffset(long) {}
int closedAngle(uint8_t) { return 0; }
void setClosedAngle(uint8_t, int) {}
String inflightCommand() { return String(""); }
void setInflightCommand(const String&) {}
String lastExecutedCommand() { return String(""); }
void setLastExecutedCommand(const String&) {}
}
// Fake scale methods (header is the real one).
void Scale::begin() {}
bool Scale::update() { return true; }
void Scale::tare() { _grams = 0; }
float Scale::calibrateWithKnownWeight(float) { return 0; }
void Scale::setFactor(float f) { _factor = f; }
static std::deque<std::pair<unsigned long, float>> history;
bool Scale::stable(unsigned long w, float tol) const {
  float lo = 1e9, hi = -1e9; unsigned long oldest = fakeMillis;
  for (auto& h : history) if (fakeMillis - h.first <= w) { lo = std::min(lo, h.second); hi = std::max(hi, h.second); oldest = std::min(oldest, h.first); }
  return fakeMillis - oldest >= w * 3 / 4 && hi - lo <= tol;
}
float Scale::average(unsigned long) const { return _grams; }

// Advance simulated time by 10 ms per step; HX711 samples every 100 ms.
static void step() {
  fakeMillis += 10;
  if (gate) falling.push_back({fakeMillis, flowGps * 0.01f});
  while (!falling.empty() && fakeMillis - falling.front().first >= 300) { bowl += falling.front().second; falling.pop_front(); }
  if (fakeMillis % 100 == 0 && !sensorDead) {
    scale._grams = bowl + (jumpAt >= 0 && bowl > jumpAt ? 500 : 0);
    scale._lastSampleMs = fakeMillis;
    scale._ready = true;
    history.push_back({fakeMillis, scale._grams});
    while (history.size() > 200) history.pop_front();
  }
  if (sensorDead && fakeMillis - scale._lastSampleMs > 600) scale._ready = false;
  dispenser::tick();
}

static Result run(float target, const char* label, void (*during)(unsigned long) = nullptr) {
  shared = Shared();
  Command c;
  strlcpy(c.id, label, sizeof c.id);
  c.type = CmdType::Dispense; c.targetG = target; c.servoChannel = 0; c.openAngle = 90; c.closedAngle = 0;
  unsigned long started = fakeMillis;
  dispenser::start(c);
  while (dispenser::busy() && fakeMillis - started < 200000) {
    step();
    if (during) during(fakeMillis - started);
  }
  return shared.result;
}

static int failures = 0;
static void check(bool ok, const char* what) { printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what); if (!ok) failures++; }
static void reset(float flow) { gate = false; sensorDead = false; bowl = 0; falling.clear(); history.clear(); flowGps = flow; jumpAt = -1;
  scale._factor = 1; scale._grams = 0; scale._ready = true; scale._lastSampleMs = fakeMillis; for (int i = 0; i < 200; i++) step(); }

int main() {
  dispenser::begin();

  puts("1. Normal 100 g dispense with food still falling after close");
  reset(20);
  Result r = run(100, "normal");
  printf("     measured %.1f g in %u ms (%s)\n", r.dispensedG, r.durationMs, r.status);
  check(!strcmp(r.status, "completed"), "status completed");
  check(r.hasDispensed && fabsf(r.dispensedG - 100) <= 5, "measured within 5 g of target (in-flight compensation works)");
  check(!gate, "gate closed at the end");

  puts("2. Small 10 g dispense uses pulses only");
  reset(20);
  r = run(10, "small");
  printf("     measured %.1f g (%s)\n", r.dispensedG, r.status);
  check(r.hasDispensed && r.dispensedG > 0 && r.dispensedG < 20, "small amount does not overshoot badly");
  check(!gate, "gate closed");

  puts("3. Empty container: no weight increase");
  reset(0);
  r = run(100, "empty");
  check(!strcmp(r.status, "failed") && !strcmp(r.errorCode, "no_flow"), "fails with no_flow");
  check(!gate, "gate closed");

  puts("4. Load cell dies mid-dispense");
  reset(20);
  r = run(100, "sensor", [](unsigned long t) { if (t > 3000) sensorDead = true; });
  check(!strcmp(r.status, "failed") && !strcmp(r.errorCode, "sensor_timeout"), "fails with sensor_timeout");
  check(!r.hasDispensed, "does not claim a weight it could not measure");
  check(!gate, "gate closed");

  puts("5. Emergency stop mid-dispense");
  reset(20);
  r = run(200, "estop", [](unsigned long t) { if (t > 3000) shared.abortRequested = true; });
  printf("     measured %.1f g before stop\n", r.dispensedG);
  check(!strcmp(r.status, "cancelled"), "status cancelled");
  check(r.hasDispensed && r.dispensedG > 0 && r.dispensedG < 200, "reports what actually landed");
  check(!gate, "gate closed");

  puts("6. Very slow flow hits the maximum duration");
  reset(1.2f);  // 1.2 g/s keeps rising, so no_flow does not trigger
  r = run(100, "slow");
  check(!strcmp(r.status, "failed") && !strcmp(r.errorCode, "timeout"), "fails with timeout");
  check(r.durationMs < 45000 + 7000, "stops within max duration + settle time");
  check(!gate, "gate closed");

  puts("7. Implausible reading (e.g. someone leans on the scale)");
  reset(20);
  jumpAt = 40;
  r = run(100, "jump");
  check(!strcmp(r.status, "failed") && !strcmp(r.errorCode, "sensor_implausible"), "fails with sensor_implausible");
  check(!gate, "gate closed");

  puts("8. Server sends an absurd max duration; firmware clamps it");
  reset(0.5f);
  Shared tmp; (void)tmp;
  {
    shared = Shared();
    Command c; strlcpy(c.id, "clamp", sizeof c.id); c.type = CmdType::Dispense; c.targetG = 100; c.servoChannel = 0; c.openAngle = 90;
    c.settings.maxDurationMs = 10000000; c.settings.noFlowTimeoutMs = 10000000;
    unsigned long s0 = fakeMillis; dispenser::start(c);
    while (dispenser::busy() && fakeMillis - s0 < 400000) step();
    check(fakeMillis - s0 <= 120000 + 31000, "stopped by the 120 s hard limit");
    check(!gate, "gate closed");
  }

  printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "ALL PASSED", failures, failures == 1 ? "" : "s");
  return failures ? 1 : 0;
}
