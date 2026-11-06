/*
 Network task (core 0). Nothing here is compiled-in per device: Wi-Fi, server address and
 device credentials are learned at runtime and kept in flash (NVS).

   no Wi-Fi saved ----------> setup hotspot "DietBalancer-XXXX" + setup page (192.168.4.1)
   Wi-Fi saved -------------> connect (setup hotspot reopens if it fails for 60 s)
   connected, no server ----> find the backend with mDNS (_dietbalancer._tcp), or use the
                              address typed on the setup page
   server, not paired ------> announce; show the 6-digit code; receive token when claimed
   paired ------------------> register, heartbeat, poll commands, progress, results
   token rejected 3x -------> forget token and go back to showing a pairing code
*/
#include "net.h"
#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_random.h>
#include "config.h"
#include "display.h"
#include "provision.h"
#include "servos.h"
#include "shared.h"
#include "storage.h"

namespace {
String resetReason, interruptedCmd;
String hwId, apSsid, apPassword;
String baseUrl;                 // e.g. http://192.168.1.20:8000/api/v1
bool baseUrlDiscovered = false; // true if found by mDNS (re-discover after repeated failures)
String deviceId, deviceToken;   // empty until paired
String pairingSecret;           // random per pairing attempt, never leaves this device except to the server
unsigned long lastHeartbeat = 0, lastPoll = 0, lastProgress = 0, lastRegisterTry = 0, lastWifiTry = 0;
unsigned long lastDiscovery = 0, discoveryStarted = 0, wifiDownSince = 0, lastAnnounce = 0, announceInterval = 3000;
unsigned long resultRetryAt = 0;
uint8_t resultFailures = 0, consecutiveFailures = 0, authFailures = 0;
bool registered = false, mdnsStarted = false;

void setMode(NetMode m) {
  SHARED_LOCK();
  shared.mode = m;
  SHARED_UNLOCK();
}

void newLocalCode() {
  char code[7];
  snprintf(code, sizeof(code), "%06lu", (unsigned long)(esp_random() % 1000000UL));
  SHARED_LOCK();
  strlcpy(shared.pairingCode, code, sizeof(shared.pairingCode));
  shared.paired = false;
  SHARED_UNLOCK();
}

void setPairingCode(const char* code) {
  SHARED_LOCK();
  strlcpy(shared.pairingCode, code ? code : "", sizeof(shared.pairingCode));
  SHARED_UNLOCK();
}

void markServer(int code) {
  bool reachable = code > 0;
  consecutiveFailures = reachable ? 0 : consecutiveFailures + 1;
  SHARED_LOCK();
  shared.serverOk = consecutiveFailures < 3;
  shared.authFailed = code == 401;
  SHARED_UNLOCK();
}

int lastHttpCode = 0;  // for diagnostics

int request(const char* method, const String& path, const String& body, JsonDocument* out, bool auth = true) {
  if (WiFi.status() != WL_CONNECTED || !baseUrl.length()) return -1;
  String url = baseUrl + path;
  // The network clients MUST be declared before HTTPClient: C++ destroys objects in
  // reverse order, and HTTPClient's destructor still uses its client.
  WiFiClient plain;
#ifdef API_ROOT_CA
  WiFiClientSecure secure;
  secure.setCACert(API_ROOT_CA);
#endif
  HTTPClient http;
  http.setReuse(false);  // one request per connection: simplest and most robust here
#ifdef API_ROOT_CA
  bool ok = url.startsWith("https") ? http.begin(secure, url) : http.begin(plain, url);
#else
  if (url.startsWith("https")) {
    setLastError("https needs API_ROOT_CA");
    return -2;
  }
  bool ok = http.begin(plain, url);
#endif
  if (!ok) {
    http.end();
    return -3;
  }
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");
  if (auth && deviceToken.length()) {
    http.addHeader("X-Device-Id", deviceId);
    http.addHeader("X-Device-Token", deviceToken);
  }
  int code = http.sendRequest(method, body);
  if (code > 0 && out && http.getSize() != 0) {
    String payload = http.getString();
    if (payload.length()) deserializeJson(*out, payload);
  }
  http.end();
  lastHttpCode = code;
  markServer(code);
  return code;
}

// Explains an HTTP result in plain words for the serial log.
String describe(int code) {
  if (code > 0) return String("HTTP ") + code;
  if (code == -1 && WiFi.status() != WL_CONNECTED) return "Wi-Fi not connected";
  return String(code) + " (" + HTTPClient::errorToString(code) + ")";
}

// Serial "nettest": step-by-step check of the path to the server.
void runNetTest() {
  Serial.println("---- nettest ----");
  Serial.printf("Wi-Fi: %s, IP %s, gateway %s, RSSI %d\n", WiFi.status() == WL_CONNECTED ? "connected" : "NOT connected",
                WiFi.localIP().toString().c_str(), WiFi.gatewayIP().toString().c_str(), WiFi.RSSI());
  Serial.printf("Server URL: %s\n", baseUrl.length() ? baseUrl.c_str() : "(none yet)");
  if (!baseUrl.length() || WiFi.status() != WL_CONNECTED) return;
  // Parse host and port from http://host:port/...
  String rest = baseUrl.substring(baseUrl.indexOf("://") + 3);
  String hostPort = rest.substring(0, rest.indexOf('/') < 0 ? rest.length() : rest.indexOf('/'));
  String host = hostPort;
  uint16_t port = 80;
  if (hostPort.indexOf(':') >= 0) {
    host = hostPort.substring(0, hostPort.indexOf(':'));
    port = hostPort.substring(hostPort.indexOf(':') + 1).toInt();
  }
  {
    WiFiClient gw;
    bool gwOk = gw.connect(WiFi.gatewayIP(), 80, 2000);
    gw.stop();
    Serial.printf("1) Router %s port 80: %s\n", WiFi.gatewayIP().toString().c_str(),
                  gwOk ? "reachable" : "no answer (normal for some routers)");
  }
  {
    WiFiClient c;
    unsigned long t = millis();
    bool tcp = c.connect(host.c_str(), port, 3000);
    c.stop();
    Serial.printf("2) TCP connect to %s:%u: %s (%lu ms)\n", host.c_str(), port, tcp ? "OK" : "FAILED", millis() - t);
    if (!tcp) {
      Serial.println("   -> The laptop is not accepting connections from this ESP32.");
      Serial.println("      Check: Windows firewall, router 'AP/client isolation', or a VPN such as ZeroTier.");
    }
  }
  String healthUrl = baseUrl.substring(0, baseUrl.indexOf("/api/")) + "/health";
  {
    WiFiClient c;
    HTTPClient h;
    h.setReuse(false);
    h.begin(c, healthUrl);
    h.setConnectTimeout(3000);
    h.setTimeout(3000);
    int code = h.GET();
    String body = code > 0 ? h.getString() : "";
    h.end();
    Serial.printf("3) GET %s -> %s %s\n", healthUrl.c_str(), describe(code).c_str(), body.c_str());
  }
  Serial.printf("4) Last pairing/API request result: %s\n", describe(lastHttpCode).c_str());
  Serial.println("-----------------");
}

String devicePath(const char* suffix) { return String("/devices/") + deviceId + suffix; }

// ---- unpair handling ------------------------------------------------------------
void forgetCredentials(const char* why) {
  Serial.printf("[pair] %s: forgetting this dispenser's connection; showing a new pairing code\n", why);
  storage::clearDeviceCredentials();
  deviceId = "";
  deviceToken = "";
  registered = false;
  pairingSecret = "";
  authFailures = 0;
  newLocalCode();
  SHARED_LOCK();
  shared.registered = false;
  shared.serverEstop = false;
  SHARED_UNLOCK();
}

void noteAuthResult(int code) {
  if (code == 401) {
    if (++authFailures >= 3) forgetCredentials("the server no longer accepts this dispenser (removed from the account?)");
  } else if (code > 0) {
    authFailures = 0;
  }
}

// ---- Wi-Fi + setup hotspot -------------------------------------------------------
void maintainWifi() {
  bool connected = WiFi.status() == WL_CONNECTED;
  SHARED_LOCK();
  bool was = shared.wifiOk;
  shared.wifiOk = connected;
  if (connected) strlcpy(shared.ip, WiFi.localIP().toString().c_str(), sizeof(shared.ip));
  SHARED_UNLOCK();
  if (connected) {
    wifiDownSince = 0;
    if (!was) {
      Serial.printf("[wifi] connected to %s, IP %s, RSSI %d\n", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
      mdnsStarted = false;
    }
    return;
  }
  if (was) {
    Serial.println("[wifi] connection lost");
    registered = false;
  }
  if (!wifiDownSince) wifiDownSince = millis();
  setMode(NetMode::ConnectingWifi);
  if (millis() - lastWifiTry > WIFI_RETRY_MS || lastWifiTry == 0) {
    lastWifiTry = millis();
    String ssid = storage::wifiSsid();
    Serial.printf("[wifi] connecting to %s...\n", ssid.c_str());
    WiFi.disconnect();
    WiFi.begin(ssid.c_str(), storage::wifiPassword().c_str());
  }
  // Can't join for a minute (wrong password, moved house...): reopen the setup page too.
  if (millis() - wifiDownSince > 60000 && !provision::running() && !strlen(WIFI_SSID)) {
    Serial.println("[wifi] still not connected after 60 s; opening the setup hotspot as well");
    provision::start(apSsid, apPassword);
  }
}

// ---- server discovery ------------------------------------------------------------
void discoverServer() {
  String manual = storage::serverUrl();
  if (manual.length()) {
    baseUrl = manual;
    baseUrlDiscovered = false;
    return;
  }
  setMode(NetMode::FindingServer);
  if (!discoveryStarted) discoveryStarted = millis();
  if (millis() - lastDiscovery < 5000 && lastDiscovery) return;
  lastDiscovery = millis();
  if (!mdnsStarted) {
    String host = "dietbalancer-" + hwId.substring(hwId.length() - 4);
    host.toLowerCase();
    MDNS.end();
    mdnsStarted = MDNS.begin(host.c_str());
  }
  int n = MDNS.queryService("dietbalancer", "tcp");
  for (int i = 0; i < n; i++) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    IPAddress ip = MDNS.address(i);
#else
    IPAddress ip = MDNS.IP(i);
#endif
    uint16_t port = MDNS.port(i);
    String path = MDNS.hasTxt(i, "path") ? MDNS.txt(i, "path") : String("/api/v1");
    if (ip == IPAddress(0, 0, 0, 0) || !port) continue;
    baseUrl = "http://" + ip.toString() + ":" + String(port) + path;
    baseUrlDiscovered = true;
    discoveryStarted = 0;
    consecutiveFailures = 0;
    Serial.printf("[mdns] found Diet Balancer server at %s\n", baseUrl.c_str());
    return;
  }
  if (millis() - discoveryStarted > 60000) {
    setMode(NetMode::ServerNotFound);
    if (!provision::running() && !strlen(WIFI_SSID)) {
      Serial.println("[mdns] server not found; open the setup hotspot to type its address");
      provision::start(apSsid, apPassword);
    }
  }
}

// ---- pairing -----------------------------------------------------------------------
void announce() {
  if (millis() - lastAnnounce < announceInterval && lastAnnounce) return;
  lastAnnounce = millis();
  setMode(NetMode::Pairing);
  if (!pairingSecret.length()) {
    char buf[49];
    for (int i = 0; i < 24; i++) snprintf(buf + i * 2, 3, "%02x", (unsigned)(esp_random() & 0xFF));
    pairingSecret = buf;
  }
  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();
  JsonDocument body;
  body["hardware_id"] = hwId;
  body["pairing_secret"] = pairingSecret;
  body["firmware_version"] = FIRMWARE_VERSION;
  body["servo_count"] = SERVO_COUNT;
  body["hx711_ready"] = s.scaleReady;
  body["oled_ready"] = display::ok();
  body["calibrated"] = s.calibrated;
  body["local_ip"] = WiFi.localIP().toString();
  body["device_name"] = DEVICE_NAME;
  if (s.pairingCode[0]) body["pairing_code"] = s.pairingCode;  // the code already on the OLED
  String json;
  serializeJson(body, json);
  JsonDocument resp;
  int code = request("POST", "/devices/pairing/announce", json, &resp, false);
  if (code != 200) {
    static unsigned long lastLog = 0;
    if (millis() - lastLog > 15000 || !lastLog) {
      lastLog = millis();
      Serial.printf("[pair] can't reach %s: %s  (type 'nettest' for details)\n", baseUrl.c_str(), describe(code).c_str());
    }
    if (code <= 0 && baseUrlDiscovered && consecutiveFailures >= 5) baseUrl = "";  // server moved: search again
    return;
  }
  if (provision::running()) provision::stop();  // the server is reachable; setup page no longer needed
  announceInterval = (unsigned long)(resp["poll_interval"] | 3) * 1000UL;
  const char* status = resp["status"] | "";
  const char* token = resp["device_token"] | "";
  const char* id = resp["device_id"] | "";
  if (strcmp(status, "paired") == 0 && token[0] && id[0]) {
    storage::setDeviceCredentials(id, token);
    deviceId = id;
    deviceToken = token;
    pairingSecret = "";
    setPairingCode("");
    SHARED_LOCK();
    shared.paired = true;
    SHARED_UNLOCK();
    registered = false;
    lastRegisterTry = 0;
    Serial.printf("[pair] connected to an account as '%s'\n", (const char*)(resp["device_name"] | "dispenser"));
    display::message("Connected!", resp["device_name"] | "Finishing setup...");
    return;
  }
  const char* pc = resp["pairing_code"] | "";
  if (pc[0]) {
    SHARED_LOCK();
    bool changed = strcmp(shared.pairingCode, pc) != 0;
    SHARED_UNLOCK();
    if (changed) Serial.printf("[pair] server assigned a different code: %.3s %.3s\n", pc, pc + 3);
    setPairingCode(pc);
  }
}

// ---- paired operation (unchanged protocol) -------------------------------------------
void applyConfig(JsonDocument& doc) {
  bool estop = doc["emergency_stop_active"] | false;
  for (JsonObject c : doc["containers"].as<JsonArray>()) {
    int ch = c["servo_channel"] | -1;
    int closed = c["closed_angle"] | -1;
    if (ch >= 0 && ch < SERVO_COUNT && closed >= 0) servos::setClosedAngle(ch, closed);
  }
  SHARED_LOCK();
  shared.serverEstop = estop;
  SHARED_UNLOCK();
}

void tryRegister() {
  if (millis() - lastRegisterTry < REGISTER_RETRY_MS && lastRegisterTry != 0) return;
  lastRegisterTry = millis();
  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();
  JsonDocument body;
  body["firmware_version"] = FIRMWARE_VERSION;
  body["servo_count"] = SERVO_COUNT;
  body["hx711_ready"] = s.scaleReady;
  body["oled_ready"] = display::ok();
  body["calibrated"] = s.calibrated;
  body["ip_address"] = WiFi.localIP().toString();
  body["wifi_rssi"] = WiFi.RSSI();
  body["reset_reason"] = resetReason;
  if (interruptedCmd.length()) body["interrupted_command_id"] = interruptedCmd;
  String json;
  serializeJson(body, json);
  JsonDocument resp;
  int code = request("POST", "/devices/register", json, &resp);
  noteAuthResult(code);
  if (code == 200) {
    registered = true;
    applyConfig(resp);
    if (interruptedCmd.length()) {
      storage::setInflightCommand("");
      interruptedCmd = "";
    }
    SHARED_LOCK();
    shared.registered = true;
    SHARED_UNLOCK();
    setLastError("");
    setMode(NetMode::Ready);
    if (provision::running()) provision::stop();
    Serial.println("[api] registered with the server");
  } else {
    Serial.printf("[api] register failed (%d)\n", code);
    if (code <= 0) {
      setLastError("Server unreachable");
      if (baseUrlDiscovered && consecutiveFailures >= 5) baseUrl = "";
    }
  }
}

void heartbeat() {
  lastHeartbeat = millis();
  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();
  JsonDocument body;
  body["state"] = s.active ? s.phase : (s.localEstop || s.serverEstop ? "stopped" : (s.lastError[0] && !s.scaleReady ? "error" : "idle"));
  if (s.scaleReady && s.calibrated) body["weight_g"] = roundf(s.weightG * 10) / 10;
  body["hx711_ready"] = s.scaleReady;
  body["wifi_rssi"] = WiFi.RSSI();
  body["ip_address"] = WiFi.localIP().toString();
  body["uptime_s"] = millis() / 1000;
  body["free_heap"] = ESP.getFreeHeap();
  if (s.lastError[0]) body["last_error"] = s.lastError;
  String json;
  serializeJson(body, json);
  JsonDocument resp;
  int code = request("POST", "/devices/heartbeat", json, &resp);
  noteAuthResult(code);
  if (code == 200) {
    bool estop = resp["emergency_stop_active"] | false;
    SHARED_LOCK();
    shared.serverEstop = estop;
    if (estop) shared.abortRequested = true;
    SHARED_UNLOCK();
  } else if (code <= 0) {
    registered = false;  // re-register once the server is back
    if (baseUrlDiscovered && consecutiveFailures >= 5) baseUrl = "";
  }
}

void sendProgress() {
  lastProgress = millis();
  Shared s;
  SHARED_LOCK();
  s = shared;
  SHARED_UNLOCK();
  if (!s.command.id[0]) return;
  JsonDocument body;
  body["weight_g"] = roundf(s.weightG * 10) / 10;
  body["phase"] = s.phase;
  String json;
  serializeJson(body, json);
  JsonDocument resp;
  int code = request("POST", devicePath("/commands/") + s.command.id + "/progress", json, &resp);
  if (code == 200 && (resp["abort"] | false)) {
    SHARED_LOCK();
    shared.abortRequested = true;
    SHARED_UNLOCK();
    Serial.printf("[api] server asked to stop (%s)\n", (const char*)(resp["reason"] | "unknown"));
  }
}

void sendResult() {
  if (millis() < resultRetryAt) return;
  Result r;
  SHARED_LOCK();
  r = shared.result;
  SHARED_UNLOCK();
  JsonDocument body;
  body["status"] = r.status;
  if (r.hasStart) body["start_weight_g"] = roundf(r.startG * 10) / 10;
  if (r.hasFinal) body["final_weight_g"] = roundf(r.finalG * 10) / 10;
  if (r.hasDispensed) body["dispensed_weight_g"] = roundf(r.dispensedG * 10) / 10;
  body["duration_ms"] = r.durationMs;
  if (r.errorCode[0]) body["error_code"] = r.errorCode;
  if (r.errorMessage[0]) body["error_message"] = r.errorMessage;
  String json;
  serializeJson(body, json);
  int code = request("POST", devicePath("/commands/") + r.commandId + "/result", json, nullptr);
  if ((code >= 200 && code < 300) || code == 404 || code == 409 || code == 422) {
    SHARED_LOCK();
    shared.resultPending = false;
    shared.command.id[0] = 0;
    SHARED_UNLOCK();
    storage::setInflightCommand("");
    resultFailures = 0;
    Serial.printf("[api] result delivered (%d)\n", code);
  } else {
    resultFailures = min<uint8_t>(resultFailures + 1, 6);
    resultRetryAt = millis() + (1000UL << resultFailures);
    Serial.printf("[api] result not delivered (%d), retrying\n", code);
  }
}

bool parseCommand(JsonDocument& doc, Command& c) {
  const char* id = doc["command_id"];
  const char* type = doc["type"];
  if (!id || !type || strlen(id) >= sizeof(c.id)) return false;
  strlcpy(c.id, id, sizeof(c.id));
  c.type = strcmp(type, "tare") == 0 ? CmdType::Tare : CmdType::Dispense;
  c.targetG = doc["target_weight_g"] | 0.0f;
  c.servoChannel = doc["servo_channel"] | -1;
  c.openAngle = doc["open_angle"] | 0;
  c.closedAngle = doc["closed_angle"] | 0;
  JsonObject s = doc["settings"];
  c.settings.inflightG = s["inflight_g"] | c.settings.inflightG;
  c.settings.slowdownG = s["slowdown_g"] | c.settings.slowdownG;
  c.settings.pulseOpenMs = s["pulse_open_ms"] | c.settings.pulseOpenMs;
  c.settings.pulseSettleMs = s["pulse_settle_ms"] | c.settings.pulseSettleMs;
  c.settings.toleranceG = s["tolerance_g"] | c.settings.toleranceG;
  c.settings.maxDurationMs = s["max_duration_ms"] | c.settings.maxDurationMs;
  c.settings.noFlowTimeoutMs = s["no_flow_timeout_ms"] | c.settings.noFlowTimeoutMs;
  c.settings.stableToleranceG = s["stable_tolerance_g"] | c.settings.stableToleranceG;
  c.settings.stableWindowMs = s["stable_window_ms"] | c.settings.stableWindowMs;
  c.settings.settleTimeoutMs = s["settle_timeout_ms"] | c.settings.settleTimeoutMs;
  c.settings.tolerancePct = s["tolerance_percent"] | c.settings.tolerancePct;
  c.settings.maxOvershootPct = s["max_overshoot_percent"] | c.settings.maxOvershootPct;
  strlcpy(c.label, doc["label"] | "", sizeof(c.label));
  c.mealPos = doc["meal_position"] | 0;
  c.mealTotal = doc["meal_total"] | 0;
  return c.type == CmdType::Tare || (c.targetG > 0 && c.servoChannel >= 0);
}

void pollForCommand() {
  lastPoll = millis();
  JsonDocument doc;
  int code = request("GET", devicePath("/commands/next"), "", &doc);
  noteAuthResult(code);
  if (code != 200) return;
  Command c;
  if (!parseCommand(doc, c)) {
    setLastError("Malformed command ignored");
    return;
  }
  if (storage::lastExecutedCommand() == c.id) return;
  JsonDocument ack;
  int ackCode = request("POST", devicePath("/commands/") + c.id + "/ack", "", &ack);
  if (ackCode != 200 || (ack["abort"] | false)) {
    Serial.printf("[api] command %s not executed (ack %d)\n", c.id, ackCode);
    return;
  }
  SHARED_LOCK();
  shared.command = c;
  shared.commandReady = true;
  shared.abortRequested = false;
  SHARED_UNLOCK();
  Serial.printf("[api] command %s accepted: %s %.1f g of '%s' on servo %d", c.id,
                c.type == CmdType::Tare ? "tare" : "dispense", c.targetG, c.label, c.servoChannel);
  if (c.mealTotal) Serial.printf(" (meal step %u of %u)", c.mealPos, c.mealTotal);
  Serial.println();
}

void reportLocalEstop() {
  JsonDocument body;
  body["reason"] = "Triggered on the device";
  String json;
  serializeJson(body, json);
  if (request("POST", devicePath("/emergency-stop"), json, nullptr) == 200) {
    SHARED_LOCK();
    shared.estopToReport = false;
    SHARED_UNLOCK();
  }
}

void handleConsoleRequests() {
  SHARED_LOCK();
  bool unpair = shared.unpairRequested, forgetWifi = shared.forgetWifiRequested, test = shared.netTestRequested;
  shared.unpairRequested = shared.forgetWifiRequested = shared.netTestRequested = false;
  SHARED_UNLOCK();
  if (test) runNetTest();
  if (unpair) forgetCredentials("unpair requested on the serial console");
  if (forgetWifi) {
    storage::setWifi("", "");
    Serial.println("[wifi] Wi-Fi forgotten; restarting into setup mode");
    vTaskDelay(pdMS_TO_TICKS(500));
    ESP.restart();
  }
}

void netTask(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  for (;;) {
    provision::loop();
    handleConsoleRequests();
    if (provision::saveRequested()) {
      vTaskDelay(pdMS_TO_TICKS(1500));  // let the "Saved" page reach the phone
      ESP.restart();
    }
    if (!storage::wifiSsid().length()) {
      setMode(NetMode::WifiSetup);
      if (!provision::running()) provision::start(apSsid, apPassword);
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    maintainWifi();
    if (WiFi.status() == WL_CONNECTED) {
      if (!baseUrl.length()) discoverServer();
      if (baseUrl.length()) {
        Shared s;
        SHARED_LOCK();
        s = shared;
        SHARED_UNLOCK();
        unsigned long now = millis();
        if (!deviceToken.length()) {
          if (provision::running() && storage::serverUrl().length() == 0 && baseUrlDiscovered) provision::stop();
          announce();
        } else {
          if (s.estopToReport) reportLocalEstop();
          if (!registered) {
            tryRegister();
          } else {
            setMode(NetMode::Ready);
            if (s.resultPending) sendResult();
            if (s.active && now - lastProgress >= PROGRESS_INTERVAL_MS) sendProgress();
            if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) heartbeat();
            bool canTakeWork = registered && !s.active && !s.commandReady && !s.resultPending && !s.serverEstop && !s.localEstop;
            if (canTakeWork && now - lastPoll >= POLL_INTERVAL_MS) pollForCommand();
          }
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(provision::running() ? 10 : 50));
  }
}
}  // namespace

namespace net {
String hardwareId() {
  // Read from the chip's eFuse: always available (WiFi.macAddress() can return zeros
  // on newer cores if called before the Wi-Fi driver has fully started).
  uint64_t mac = ESP.getEfuseMac();
  char buf[16];
  snprintf(buf, sizeof(buf), "DB-%02X%02X%02X", (unsigned)((mac >> 24) & 0xFF), (unsigned)((mac >> 32) & 0xFF),
           (unsigned)((mac >> 40) & 0xFF));
  return buf;
}

void startTask(const char* reason, const String& interrupted) {
  resetReason = reason;
  interruptedCmd = interrupted;
  WiFi.mode(WIFI_STA);  // MAC is readable once the Wi-Fi driver is up
  hwId = hardwareId();
  apSsid = "DietBalancer-" + hwId.substring(hwId.length() - 4);
  apPassword = storage::setupApPassword();
  deviceId = storage::deviceId();
  deviceToken = storage::deviceToken();
  if (!deviceToken.length()) {
    newLocalCode();
    char pc[7];
    SHARED_LOCK();
    strlcpy(pc, shared.pairingCode, sizeof(pc));
    SHARED_UNLOCK();
    Serial.printf("[pair] not connected to an account yet. Pairing code: %.3s %.3s\n", pc, pc + 3);
    Serial.println("[pair] In the web app: Smart Dispenser -> Connect a dispenser -> tap it -> enter the code.");
  }
  SHARED_LOCK();
  shared.paired = deviceToken.length() > 0;
  strlcpy(shared.apSsid, apSsid.c_str(), sizeof(shared.apSsid));
  strlcpy(shared.apPassword, apPassword.c_str(), sizeof(shared.apPassword));
  strlcpy(shared.hardwareId, hwId.c_str(), sizeof(shared.hardwareId));
  SHARED_UNLOCK();
  Serial.printf("Hardware id %s, paired: %s\n", hwId.c_str(), deviceToken.length() ? "yes" : "no");
  xTaskCreatePinnedToCore(netTask, "net", 12288, nullptr, 1, nullptr, 0);
}
}  // namespace net
