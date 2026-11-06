/*
 Dispensing strategy (all thresholds come from the server, clamped to hard limits):

   PREPARE      wait for a stable reading (bounded by settle_timeout) -> start weight
   FLOWING      gate open continuously until (target - slowdown_g)
   PULSE_*      short open pulses; after each settle pause, stop once within tolerance/2
   FINAL_SETTLE gate closed; wait for food still falling + a stable reading
   -> report the MEASURED weight (final - start)

 Every tick, whatever the state:
   * abort (cancel / emergency stop) -> close, then measure and report "cancelled"
   * total time > max duration        -> close, measure, report "failed: timeout"
   * no HX711 sample for 600 ms       -> close immediately, report "failed: sensor_timeout"
   * implausible jump / bowl removed  -> close immediately, report failure, no weight claimed
   * gate open but no weight increase for no_flow_timeout -> close, report "failed: no_flow"
 A gate is never opened unless the scale is ready, calibrated, and the servo's closed
 angle is known. Nothing here blocks: there are no delay() calls in this file.
*/
#include "dispenser.h"
#include "config.h"
#include "scale.h"
#include "servos.h"
#include "storage.h"

namespace {
enum class Phase { Idle, Prepare, Flowing, PulseOpen, PulseClosed, FinalSettle };

Phase phase = Phase::Idle;
Command cmd;
unsigned long t0 = 0, phaseStart = 0, openSinceRiseMs = 0, lastTick = 0;
float startG = 0, peakG = 0, lastG = 0;
bool gateOpen = false;
// Outcome decided before the final settle (cancelled / failed), or empty for "decide by weight".
char pendingStatus[12] = "";
char pendingCode[32] = "";
char pendingMsg[120] = "";

void setPhase(Phase p) {
  phase = p;
  phaseStart = millis();
  const char* name = dispenser::phaseName();
  SHARED_LOCK();
  strlcpy(shared.phase, name, sizeof(shared.phase));
  shared.active = p != Phase::Idle;
  SHARED_UNLOCK();
}

void openGate() {
  servos::open(cmd.servoChannel, cmd.openAngle);
  gateOpen = true;
}

void closeGate() {
  servos::closeAll();  // close everything, not just the active channel
  gateOpen = false;
}

void finish(const char* status, const char* code, const char* msg, bool haveWeights, float finalG) {
  closeGate();
  Result r;
  strlcpy(r.commandId, cmd.id, sizeof(r.commandId));
  strlcpy(r.status, status, sizeof(r.status));
  if (code) strlcpy(r.errorCode, code, sizeof(r.errorCode));
  if (msg) strlcpy(r.errorMessage, msg, sizeof(r.errorMessage));
  r.durationMs = millis() - t0;
  if (haveWeights) {
    r.hasStart = r.hasFinal = r.hasDispensed = true;
    r.startG = startG;
    r.finalG = finalG;
    r.dispensedG = cmd.type == CmdType::Tare ? 0 : finalG - startG;
  }
  SHARED_LOCK();
  shared.result = r;
  shared.resultPending = true;
  shared.abortRequested = false;
  SHARED_UNLOCK();
  storage::setLastExecutedCommand(cmd.id);
  Serial.printf("[dispense] %s %s %s dispensed=%s\n", status, code ? code : "", msg ? msg : "",
                haveWeights ? String(r.dispensedG, 1).c_str() : "unknown");
  pendingStatus[0] = pendingCode[0] = pendingMsg[0] = 0;
  setPhase(Phase::Idle);
}

// Stop immediately but still measure what landed in the bowl.
void stopAndSettle(const char* status, const char* code, const char* msg) {
  closeGate();
  strlcpy(pendingStatus, status, sizeof(pendingStatus));
  strlcpy(pendingCode, code, sizeof(pendingCode));
  strlcpy(pendingMsg, msg, sizeof(pendingMsg));
  setPhase(Phase::FinalSettle);
}

float dispensedNow() { return scale.grams() - startG; }
}  // namespace

namespace dispenser {
void begin() { setPhase(Phase::Idle); }

bool busy() { return phase != Phase::Idle; }
float target() { return cmd.targetG; }
float dispensedSoFar() { return phase == Phase::Idle || phase == Phase::Prepare ? 0 : max(0.0f, dispensedNow()); }

const char* label() { return cmd.label; }
uint8_t mealPos() { return cmd.mealPos; }
uint8_t mealTotal() { return cmd.mealTotal; }

const char* phaseName() {
  switch (phase) {
    case Phase::Prepare: return "preparing";
    case Phase::Flowing: return "dispensing";
    case Phase::PulseOpen:
    case Phase::PulseClosed: return "topping up";
    case Phase::FinalSettle: return "settling";
    default: return "idle";
  }
}

bool start(const Command& c) {
  cmd = c;
  t0 = millis();
  startG = peakG = lastG = 0;
  lastTick = 0;
  openSinceRiseMs = 0;
  pendingStatus[0] = pendingCode[0] = pendingMsg[0] = 0;
  // Clamp everything the server sent to the firmware's hard limits.
  DispenseSettings& s = cmd.settings;
  s.maxDurationMs = min<uint32_t>(s.maxDurationMs, HARD_MAX_DURATION_MS);
  s.noFlowTimeoutMs = constrain(s.noFlowTimeoutMs, 1000u, 30000u);
  s.pulseOpenMs = constrain(s.pulseOpenMs, 50u, 2000u);
  s.pulseSettleMs = constrain(s.pulseSettleMs, 100u, 5000u);
  s.settleTimeoutMs = constrain(s.settleTimeoutMs, 1000u, 30000u);
  s.stableWindowMs = constrain(s.stableWindowMs, 300u, 10000u);
  s.inflightG = constrain(s.inflightG, 0.0f, 100.0f);
  s.slowdownG = max(constrain(s.slowdownG, 0.0f, 200.0f), s.inflightG);
  s.toleranceG = constrain(s.toleranceG, 0.5f, 50.0f);
  s.tolerancePct = constrain(s.tolerancePct, 1.0f, 50.0f);
  s.maxOvershootPct = constrain(s.maxOvershootPct, 5.0f, 200.0f);
  // Approximate dispensing: on target within ±tolerancePct % (at least toleranceG grams).
  s.toleranceG = max(s.toleranceG, cmd.targetG * s.tolerancePct / 100.0f);

  if (!scale.ready()) { finish("failed", "sensor_not_ready", "Load cell (HX711) is not responding.", false, 0); return false; }
  if (!scale.calibrated()) { finish("failed", "not_calibrated", "Scale is not calibrated.", false, 0); return false; }
  if (cmd.type == CmdType::Dispense) {
    if (cmd.targetG <= 0 || cmd.targetG > HARD_MAX_TARGET_G) { finish("failed", "invalid_target", "Target outside firmware limits.", false, 0); return false; }
    if (cmd.servoChannel < 0 || cmd.servoChannel >= SERVO_COUNT) { finish("failed", "invalid_servo", "Servo channel not present on this device.", false, 0); return false; }
    if (cmd.openAngle == cmd.closedAngle) { finish("failed", "invalid_angles", "Open and closed angles are equal.", false, 0); return false; }
    servos::setClosedAngle(cmd.servoChannel, cmd.closedAngle);
  }
  storage::setInflightCommand(cmd.id);  // if power is lost from here on, the next boot reports it
  setPhase(Phase::Prepare);
  return true;
}

void abort(const char* reason) {
  if (phase == Phase::Idle) { closeGate(); return; }
  if (phase == Phase::FinalSettle) return;  // already closed and measuring
  if (phase == Phase::Prepare) {          // nothing dispensed yet
    finish("cancelled", "cancelled", reason, false, 0);
    return;
  }
  stopAndSettle("cancelled", "cancelled", reason);
}

void tick() {
  if (phase == Phase::Idle) return;
  unsigned long now = millis();

  // ---- global safety checks ---------------------------------------------------
  if (now - scale.lastSampleMs() > SENSOR_TIMEOUT_MS || !scale.ready()) {
    closeGate();
    finish("failed", "sensor_timeout", "Load cell stopped responding; gate closed. Weight unknown.", false, 0);
    return;
  }
  float g = scale.grams();
  if (phase != Phase::Prepare) {
    if (fabsf(g - lastG) > MAX_JUMP_G) {
      closeGate();
      finish("failed", "sensor_implausible", "Implausible weight jump; gate closed.", false, 0);
      return;
    }
    if (g < startG - BOWL_REMOVED_DROP_G) {
      closeGate();
      finish("failed", "bowl_removed", "Weight dropped below the start; was the bowl lifted?", false, 0);
      return;
    }
  }
  lastG = g;

  bool abortReq;
  SHARED_LOCK();
  abortReq = shared.abortRequested || shared.localEstop || shared.serverEstop;
  SHARED_UNLOCK();
  if (abortReq) {
    abort("Stopped by request or emergency stop.");
    if (phase == Phase::Idle) return;
  }
  if (phase != Phase::FinalSettle && now - t0 > cmd.settings.maxDurationMs) {
    stopAndSettle("failed", "timeout", "Maximum dispensing time reached.");
  }

  // Track flow while the gate is open.
  unsigned long dt = lastTick ? now - lastTick : 0;
  lastTick = now;
  if (g > peakG + FLOW_DETECT_G) {
    peakG = g;
    openSinceRiseMs = 0;
  } else if (gateOpen) {
    openSinceRiseMs += dt;
  }
  if (gateOpen && openSinceRiseMs > cmd.settings.noFlowTimeoutMs) {
    stopAndSettle("failed", "no_flow", "Weight did not increase. The container may be empty or jammed.");
  }

  const DispenseSettings& s = cmd.settings;
  float done = g - startG;
  // Safety: never keep going far past the target (e.g. a gate that doesn't close fully).
  if (cmd.type == CmdType::Dispense && phase != Phase::Prepare && phase != Phase::FinalSettle &&
      done > cmd.targetG * (1.0f + s.maxOvershootPct / 100.0f)) {
    closeGate();                 // result is still decided by the measured weight,
    setPhase(Phase::FinalSettle);  // and the server reports it as over target
  }
  switch (phase) {
    case Phase::Prepare:
      if (scale.stable(s.stableWindowMs, s.stableToleranceG)) {
        startG = scale.average(s.stableWindowMs);
        lastG = peakG = startG;
        if (cmd.type == CmdType::Tare) {
          scale.tare();
          startG = 0;
          finish("completed", nullptr, nullptr, true, 0);
          return;
        }
        openSinceRiseMs = 0;
        lastTick = now;
        if (cmd.targetG - s.inflightG <= 0 || cmd.targetG <= s.slowdownG) {
          setPhase(Phase::PulseClosed);  // small amounts: pulses only
          phaseStart = now - s.pulseSettleMs;
        } else {
          openGate();
          setPhase(Phase::Flowing);
        }
      } else if (now - phaseStart > s.settleTimeoutMs) {
        finish("failed", "unstable_scale", "Scale reading never settled; nothing was dispensed.", false, 0);
      }
      break;

    case Phase::Flowing:
      if (done >= cmd.targetG - s.inflightG) {
        closeGate();
        setPhase(Phase::FinalSettle);
      } else if (done >= cmd.targetG - s.slowdownG) {
        closeGate();
        setPhase(Phase::PulseClosed);
      }
      break;

    case Phase::PulseOpen:
      if (done >= cmd.targetG - s.inflightG || now - phaseStart >= s.pulseOpenMs) {
        closeGate();
        setPhase(Phase::PulseClosed);
      }
      break;

    case Phase::PulseClosed:
      // After the settle pause nothing is still falling, so compare against the
      // tolerance band rather than the in-flight allowance (which would under-fill).
      if (now - phaseStart >= s.pulseSettleMs) {
        if (done >= cmd.targetG - s.toleranceG * 0.5f) {
          setPhase(Phase::FinalSettle);
        } else {
          openGate();
          setPhase(Phase::PulseOpen);
        }
      }
      break;

    case Phase::FinalSettle: {
      bool settled = now - phaseStart > 400 && scale.stable(s.stableWindowMs, s.stableToleranceG);
      bool timedOut = now - phaseStart > s.settleTimeoutMs;
      if (!settled && !timedOut) break;
      float finalG = settled ? scale.average(s.stableWindowMs) : g;
      float dispensed = finalG - startG;
      if (pendingStatus[0]) {
        finish(pendingStatus, pendingCode, pendingMsg, true, finalG);
      } else if (dispensed >= cmd.targetG - s.toleranceG) {
        finish("completed", timedOut ? "settle_timeout" : nullptr,
               timedOut ? "Reading never fully settled; last reading used." : nullptr, true, finalG);
      } else {
        finish("failed", "under_target", "Stopped below the target.", true, finalG);
      }
      break;
    }
    default:
      break;
  }
}
}  // namespace dispenser
