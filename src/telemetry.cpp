#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "sensors.h"
#include "telemetry.h"
#include "wifi_manager.h"

namespace {
constexpr char FIRMWARE_VERSION[] = "0.2.0";
constexpr uint32_t HTTP_TIMEOUT_MS = 5000;

String makeDeviceId() {
    char value[24];
    snprintf(value, sizeof(value), "esp32-%012llx", ESP.getEfuseMac());
    return String(value);
}

String deviceId = makeDeviceId();

String endpoint(const char *path) {
    return getDeviceConfig().serverUrl + path;
}

bool postJson(const String &url, const String &payload) {
    if (!isWiFiConnected()) {
        return false;
    }

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(url)) {
        Serial.printf("Unable to open HTTP connection to %s\n", url.c_str());
        return false;
    }
    http.addHeader("Content-Type", "application/json");
    const int statusCode = http.POST(payload);
    const String response = http.getString();
    http.end();

    if (statusCode < 200 || statusCode >= 300) {
        Serial.printf("POST %s failed: HTTP %d %s\n", url.c_str(), statusCode, response.c_str());
        return false;
    }
    return true;
}

void addSensor(JsonArray &sensors, const char *name, const char *key, const char *kind, const char *unit) {
    JsonObject sensor = sensors.add<JsonObject>();
    sensor["name"] = name;
    sensor["key"] = key;
    sensor["kind"] = kind;
    sensor["unit"] = unit;
}
}  // namespace

bool sendInit() {
    JsonDocument document;
    document["mac_address"] = deviceId;
    document["firmware_version"] = FIRMWARE_VERSION;
    document["ip"] = WiFi.localIP().toString();

    JsonArray sensors = document["sensors"].to<JsonArray>();
    addSensor(sensors, "Mash temperature", "mash_temperature_sensor", "temperature", "°C");
    addSensor(sensors, "Input voltage", "input_voltage_sensor", "voltage", "V");
    addSensor(sensors, "Wi-Fi signal", "wifi_rssi_sensor", "signal", "dBm");
    addSensor(sensors, "Free heap", "free_heap_sensor", "memory", "bytes");
    addSensor(sensors, "Uptime", "uptime_sensor", "duration", "s");

    String payload;
    serializeJson(document, payload);
    const bool success = postJson(endpoint("/api/v1/bootstrap/"), payload);
    Serial.println(success ? "Controller registered with B-RMS." : "B-RMS registration failed.");
    return success;
}

String buildPayload() {
    JsonDocument document;
    document["mac_address"] = deviceId;
    JsonObject metrics = document["metrics"].to<JsonObject>();
    metrics["mash_temperature_sensor"] = round(lastTemp * 100) / 100.0;
    metrics["input_voltage_sensor"] = round(voltage * 100) / 100.0;
    metrics["wifi_rssi_sensor"] = WiFi.RSSI();
    metrics["free_heap_sensor"] = ESP.getFreeHeap();
    metrics["uptime_sensor"] = millis() / 1000;

    String output;
    serializeJson(document, output);
    return output;
}

bool sendTelemetry(const String &payload) {
    const bool success = postJson(endpoint("/api/v1/telemetry/"), payload);
    if (!success) {
        Serial.println("Telemetry delivery failed.");
    }
    return success;
}
