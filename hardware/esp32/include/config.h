// Hardware configuration and firmware safety limits.
#pragma once
#include <Arduino.h>

#include "my_settings.h"  // Wi-Fi, server address, device name

#define FIRMWARE_VERSION "1.1.0"

// ---- Pins (from the verified prototype wiring) -------------------------------
// Servo "channel" N in the web app = SERVO_PINS[N].
static const uint8_t SERVO_PINS[] = {13, 14};
static const uint8_t SERVO_COUNT = sizeof(SERVO_PINS) / sizeof(SERVO_PINS[0]);

#define HX711_DT_PIN   32
#define HX711_SCK_PIN  33

#define OLED_SDA_PIN   21
#define OLED_SCL_PIN   22
#define OLED_I2C_ADDR  0x3C   // detected on the prototype (U8g2 uses the 8-bit form 0x78)

// ---- Load cell calibration --------------------------------------------------
// Raw HX711 counts per GRAM for this load cell.
// Taken from the owner's verified test sketch, which used
//   scale.set_scale(-191873.0)  ->  get_units() returned KILOGRAMS
// This firmware works in grams, so: -191873.0 / 1000 = -191.873 counts per gram.
// The negative sign is what makes added weight read positive, so HX711_INVERT stays false.
// A factor saved later with the serial command `cal <grams>` overrides this value.
#define HX711_CALIBRATION_FACTOR (-191.873f)
#define HX711_INVERT false
// Zero the scale at boot, like the test sketch did (keep the platform empty or with
// just the empty bowl while the ESP32 starts).
#define TARE_ON_BOOT true

// ---- Timing -------------------------------------------------------------------
#define HEARTBEAT_INTERVAL_MS     10000
#define POLL_INTERVAL_MS          2000
#define PROGRESS_INTERVAL_MS      1000
#define REGISTER_RETRY_MS         5000
#define WIFI_RETRY_MS             10000
#define HTTP_TIMEOUT_MS           2500
#define DISPLAY_INTERVAL_MS       300

// ---- Hard safety limits (enforced no matter what the server sends) ----------
#define HARD_MAX_DURATION_MS      120000UL  // absolute cap on one dispense
#define HARD_MAX_TARGET_G         1000.0f
#define SENSOR_TIMEOUT_MS         600       // HX711 runs at ~10 Hz; no sample for this long = failure
#define MAX_JUMP_G                300.0f    // a single-sample jump bigger than this is implausible
#define BOWL_REMOVED_DROP_G       50.0f     // weight falling this far below the start = bowl lifted
#define FLOW_DETECT_G             1.0f      // a rise of this much counts as "food is flowing"
#define STABILITY_SAMPLES         16        // ring buffer used for stability checks
