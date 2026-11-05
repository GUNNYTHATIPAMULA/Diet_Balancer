// State shared between the control loop (core 1) and the network task (core 0).
// Small structs are copied under a spinlock; nothing here blocks.
#pragma once
#include <Arduino.h>

enum class CmdType : uint8_t { Dispense, Tare };

// What the network side is doing, shown on the OLED.
enum class NetMode : uint8_t {
  Starting,
  WifiSetup,        // no Wi-Fi saved: setup hotspot + page are running
  ConnectingWifi,
  FindingServer,    // looking for the backend with mDNS
  ServerNotFound,   // gave up for now; setup page also open so an address can be typed
  Pairing,          // showing a 6-digit code, waiting for the owner to enter it
  Ready,            // paired and talking to the backend
};

struct DispenseSettings {
  float inflightG = 8, slowdownG = 25, toleranceG = 3, stableToleranceG = 1.5f;
  uint32_t pulseOpenMs = 250, pulseSettleMs = 700, maxDurationMs = 45000, noFlowTimeoutMs = 5000;
  uint32_t stableWindowMs = 1200, settleTimeoutMs = 6000;
};

struct Command {
  char id[40] = "";
  CmdType type = CmdType::Dispense;
  float targetG = 0;
  int8_t servoChannel = -1;
  int openAngle = 0, closedAngle = 0;
  DispenseSettings settings;
};

struct Result {
  char commandId[40] = "";
  char status[12] = "";          // completed | failed | cancelled
  bool hasStart = false, hasFinal = false, hasDispensed = false;
  float startG = 0, finalG = 0, dispensedG = 0;
  uint32_t durationMs = 0;
  char errorCode[32] = "";
  char errorMessage[120] = "";
};

struct Shared {
  // network -> control
  bool commandReady = false;
  Command command;
  bool abortRequested = false;   // cancel / emergency stop for the running command
  bool serverEstop = false;      // emergency stop latched on the server
  // control -> network
  bool active = false;           // a command is executing
  char phase[16] = "idle";
  float weightG = 0;
  bool scaleReady = false, calibrated = false;
  bool resultPending = false;
  Result result;
  bool localEstop = false;       // triggered from the serial console
  bool estopToReport = false;
  bool unpairRequested = false;      // serial "unpair"
  bool forgetWifiRequested = false;  // serial "wifi-reset"
  bool netTestRequested = false;     // serial "nettest"
  // status for the display
  NetMode mode = NetMode::Starting;
  char apSsid[33] = "";
  char apPassword[9] = "";
  char pairingCode[7] = "";
  bool paired = false;
  char hardwareId[16] = "";
  bool wifiOk = false, serverOk = false, registered = false, authFailed = false;
  char ip[16] = "";
  char lastError[64] = "";
};

extern Shared shared;
extern portMUX_TYPE sharedMux;

#define SHARED_LOCK() portENTER_CRITICAL(&sharedMux)
#define SHARED_UNLOCK() portEXIT_CRITICAL(&sharedMux)

void setLastError(const char* msg);
