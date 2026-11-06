// =====================================================================
//  MY SETTINGS: edit these, then click Upload.
// =====================================================================
#pragma once

// ---- Your Wi-Fi (2.4 GHz). -------------------------------------------
// Fill these in to connect without the phone setup page.
// Leave both as "" to use the setup hotspot instead (DietBalancer-XXXX).
#define WIFI_SSID      "ACT101723486083"
#define WIFI_PASSWORD  "your-wifi-password"

// ---- Your laptop/server address, including the port (8000). ----------
// Use the laptop's Wi-Fi IPv4 address from `ipconfig` (NOT localhost).
// Leave "" to find the server automatically on the network (mDNS).
#define SERVER_URL     "http://192.168.0.100:8000/api/v1"

// ---- Name shown on the OLED and in the web app's "Found nearby" list.
#define DEVICE_NAME    "Kitchen dispenser"
