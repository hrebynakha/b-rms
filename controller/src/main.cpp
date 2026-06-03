#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// ===== CONFIG =====

const char* WIFI_SSID = _WIFI_SSID;
const char* WIFI_PASS = _WIFI_PASS;

const char* SERVER_BASE = "http://beer.lan";


String deviceId;

// ===================

void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    Serial.print("Connecting WiFi");

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\nWiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
}

bool sendInit() {
    HTTPClient http;

    String url = String(SERVER_BASE) + "/api/v1/bootstrap/";

    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;

    doc["mac_address"] = deviceId;
    doc["firmware_version"] = "0.1";
    doc["ip"] = WiFi.localIP().toString();

   JsonArray sensors = doc.createNestedArray("sensors");


    JsonObject s1 = sensors.createNestedObject();
    s1["name"] = "ds18b20";
    s1["key"] = "mash_temperature_sensor";
    s1["kind"] = "temperature";
    s1["unit"] = "°C";

  
    JsonObject s2 = sensors.createNestedObject();
    s2["name"] = "esp32";
    s2["key"] = "input_voltage_sensor";
    s2["kind"] = "voltage";
    s2["unit"] = "V";

    String payload;
    serializeJson(doc, payload);

    Serial.println("Sending INIT:");
    Serial.println(payload);

    int code = http.POST(payload);

    Serial.print("HTTP code: ");
    Serial.println(code);

    String response = http.getString();
    Serial.println("Response:");
    Serial.println(response);

    http.end();

    return code > 0 && code < 300;
}

void setup() {
    Serial.begin(115200);
    delay(2000);

    deviceId = "esp32-" + String((uint32_t)ESP.getEfuseMac(), HEX);

    Serial.println("=== B-RMS BOOT ===");
    Serial.println("Device: " + deviceId);

    connectWiFi();

    bool ok = sendInit();

    if (ok) {
        Serial.println("INIT OK");
    } else {
        Serial.println("INIT FAILED");
    }
}

void loop() {
    delay(5000);
    Serial.println("alive");
}