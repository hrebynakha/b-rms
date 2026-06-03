#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>


#include "wifi_manager.h"
#include "telemetry.h"
#include "sensors.h"

void setup() {
    Serial.begin(115200);
    sensorsInit();
    
    delay(2000);
    Serial.println("=== B-RMS BOOT ===");

    connectWiFi();

    bool ok = sendInit();

    if (ok) {
        Serial.println("INIT OK");
    } else {
        Serial.println("INIT FAILED");
    }

}

void loop() {
    if (!readSensors()) {
        delay(1000);
        return;
    }

    String payload = buildPayload();
    Serial.println(payload);
    sendTelemetry(payload);

    delay(3000);
}