#include <ArduinoJson.h>
#include <HTTPClient.h>

#include "telemetry.h"
#include "wifi_manager.h"


extern float lastTemp;
extern float voltage;


String SERVER_BASE = "http://beer.lan";

String deviceId =  "esp32-" + String((uint32_t)ESP.getEfuseMac(), HEX);


bool sendInit() {
    HTTPClient http;

    String url = SERVER_BASE + "/api/v1/bootstrap/";

    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    JsonDocument doc;

    doc["mac_address"] = deviceId;
    doc["firmware_version"] = "0.1";
    doc["ip"] = WiFi.localIP().toString();

    JsonArray sensors = doc["sensors"].to<JsonArray>();


    JsonObject s1 = sensors.add<JsonObject>();
    s1["name"] = "ds18b20";
    s1["key"] = "mash_temperature_sensor";
    s1["kind"] = "temperature";
    s1["unit"] = "°C";


  
    JsonObject s2 = sensors.add<JsonObject>();
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


String buildPayload() {
    JsonDocument doc;

    doc["mac_address"] = deviceId;

    JsonObject metrics = doc["metrics"].to<JsonObject>();

    metrics["mash_temperature_sensor"] = round(lastTemp * 100) / 100.0;
    metrics["input_voltage_sensor"] = round(voltage * 100) / 100.0;

    String output;
    serializeJson(doc, output);

    return output;
}

void sendTelemetry(const String &payload) {

    if (!isWiFiConnected()) {
        Serial.println("WiFi lost");
        return;
    }

    HTTPClient http;
    http.begin(SERVER_BASE + "/api/v1/telemetry/");
    http.addHeader("Content-Type", "application/json");

    http.POST(payload);
    http.end();
}

