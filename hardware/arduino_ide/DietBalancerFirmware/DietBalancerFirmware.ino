/*
  Diet Balancer - ESP32 smart dispenser firmware (Arduino IDE version)

  This .ino is intentionally empty: setup() and loop() are in main.cpp, and the
  rest of the firmware is in the other .cpp/.h files in this folder. Arduino IDE
  compiles all of them together, so just open this file and press Upload.

  BEFORE UPLOADING: edit the "secrets.h" tab (Wi-Fi, backend LAN IP, device ID/token).

  Pins (same as your hardware test sketch):
    Servo 1 = GPIO 13 (web app "servo channel 0")
    Servo 2 = GPIO 14 (web app "servo channel 1")
    HX711 DT = GPIO 32, SCK = GPIO 33
    OLED SH1106 SDA = GPIO 21, SCL = GPIO 22 (I2C 0x3C)
  Calibration factor -191873.0 (kg) from the test sketch = -191.873 per gram (config.h).
*/
