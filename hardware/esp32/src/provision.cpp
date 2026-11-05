#include "provision.h"
#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>
#include "config.h"
#include "shared.h"
#include "storage.h"

namespace {
WebServer server(80);
DNSServer dns;
bool active = false;
bool saved = false;
bool routesAdded = false;
unsigned long lastScan = 0;
String networksHtml;

String esc(const String& in) {
  String out;
  out.reserve(in.length() + 8);
  for (char c : in) {
    if (c == '&') out += F("&amp;");
    else if (c == '<') out += F("&lt;");
    else if (c == '>') out += F("&gt;");
    else if (c == '"') out += F("&quot;");
    else if (c == '\'') out += F("&#39;");
    else out += c;
  }
  return out;
}

void scan() {
  int n = WiFi.scanNetworks(false, false);
  networksHtml = "";
  for (int i = 0; i < n && i < 20; i++) {
    String ssid = WiFi.SSID(i);
    if (!ssid.length()) continue;
    if (networksHtml.indexOf(">" + esc(ssid) + "<") >= 0) continue;  // duplicate access points
    networksHtml += "<option value=\"" + esc(ssid) + "\">" + esc(ssid) + "</option>";
  }
  WiFi.scanDelete();
  lastScan = millis();
}

const char PAGE_HEAD[] PROGMEM = R"(<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Diet Balancer setup</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#F4F7F2;color:#18261D;margin:0;padding:24px}
main{max-width:420px;margin:auto;background:#fff;border-radius:24px;padding:24px;box-shadow:0 4px 16px -6px rgba(31,95,63,.2)}
h1{font-size:24px;margin:0 0 4px}p{color:#5B6B60;line-height:1.45}label{display:block;font-weight:600;margin:16px 0 6px}
input,select{width:100%;box-sizing:border-box;font-size:16px;padding:12px;border:1px solid #E2E9E1;border-radius:12px;background:#fff}
button{width:100%;margin-top:20px;padding:14px;font-size:16px;font-weight:700;color:#fff;background:#1F5F3F;border:0;border-radius:14px}
small{color:#5B6B60}a{color:#1F5F3F}</style></head><body><main>)";

void handleRoot() {
  if (millis() - lastScan > 15000 || lastScan == 0) scan();
  String page = FPSTR(PAGE_HEAD);
  page += F("<h1>Set up your dispenser</h1><p>Choose your home Wi-Fi. Use a 2.4 GHz network.</p>"
            "<form method='post' action='/save'><label for='s'>Wi-Fi network</label><select id='s' name='ssid'>");
  page += networksHtml;
  page += F("<option value=''>Other (type below)…</option></select>"
            "<input name='ssid_manual' placeholder='Hidden network name (optional)' style='margin-top:8px'>"
            "<label for='p'>Wi-Fi password</label><input id='p' name='pass' type='password' autocomplete='off'>"
            "<label for='u'>Server address <small>(optional)</small></label>"
            "<input id='u' name='server' placeholder='Leave empty to find it automatically' value='");
  page += esc(storage::serverUrl());
  page += F("'><small>Only if automatic search fails, e.g. http://192.168.1.20:8000/api/v1</small>"
            "<button type='submit'>Save and connect</button></form>"
            "<p><a href='/'>Refresh the network list</a></p></main></body></html>");
  server.send(200, "text/html", page);
}

void handleSave() {
  String ssid = server.arg("ssid_manual");
  ssid.trim();
  if (!ssid.length()) ssid = server.arg("ssid");
  String pass = server.arg("pass");
  String url = server.arg("server");
  url.trim();
  while (url.endsWith("/")) url.remove(url.length() - 1);
  if (!ssid.length() || ssid.length() > 32 || pass.length() > 63) {
    server.send(400, "text/html", String(FPSTR(PAGE_HEAD)) +
                F("<h1>Check the details</h1><p>Choose a network (max 32 characters) and a password up to 63 characters.</p>"
                  "<p><a href='/'>Back</a></p></main></body></html>"));
    return;
  }
  if (url.length() && !url.startsWith("http://") && !url.startsWith("https://")) url = "http://" + url;
  if (url.length() && url.indexOf("/api/") < 0) url += "/api/v1";
  storage::setWifi(ssid, pass);
  storage::setServerUrl(url);
  server.send(200, "text/html", String(FPSTR(PAGE_HEAD)) +
              F("<h1>Saved</h1><p>The dispenser is restarting and joining <b>") + esc(ssid) +
              F("</b>. Reconnect this phone to your home Wi-Fi, open the Diet Balancer web app, "
                "and go to <b>Smart Dispenser → Connect a dispenser</b>. The dispenser’s screen will show a code.</p>"
                "</main></body></html>"));
  saved = true;
}

void redirect() {
  server.sendHeader("Location", "http://192.168.4.1/", true);
  server.send(302, "text/plain", "");
}
}  // namespace

namespace provision {
void start(const String& apSsid, const String& apPassword) {
  if (active) return;
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
  WiFi.softAP(apSsid.c_str(), apPassword.c_str());
  dns.start(53, "*", IPAddress(192, 168, 4, 1));  // every name -> the setup page (captive portal)
  if (!routesAdded) {
    server.on("/", HTTP_GET, handleRoot);
    server.on("/save", HTTP_POST, handleSave);
    // Phones probe these to detect a captive portal and then open the page automatically.
    server.on("/generate_204", redirect);
    server.on("/hotspot-detect.html", redirect);
    server.on("/connecttest.txt", redirect);
    server.on("/ncsi.txt", redirect);
    server.onNotFound(redirect);
    routesAdded = true;
  }
  server.begin();
  active = true;
  Serial.printf("[setup] hotspot '%s' (password %s) -> open http://192.168.4.1\n", apSsid.c_str(), apPassword.c_str());
}

void stop() {
  if (!active) return;
  server.stop();
  dns.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  active = false;
  Serial.println("[setup] hotspot closed");
}

bool running() { return active; }

void loop() {
  if (!active) return;
  dns.processNextRequest();
  server.handleClient();
}

bool saveRequested() { return saved; }
}  // namespace provision
