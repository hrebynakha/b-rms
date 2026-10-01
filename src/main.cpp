#include <Arduino.h>

#include "sensors.h"
#include "heater_output.h"
#include "telemetry.h"
#include "wifi_manager.h"

namespace {
constexpr uint32_t TELEMETRY_INTERVAL_MS = 3000;
constexpr uint32_t REGISTRATION_RETRY_MS = 10000;
constexpr uint32_t COMMAND_POLL_INTERVAL_MS = 3000;

DeviceMode deviceMode = DeviceMode::Provisioning;
bool controllerRegistered = false;
bool networkWasConnected = false;
uint32_t lastTelemetryAt = 0;
uint32_t lastRegistrationAttemptAt = 0;
uint32_t lastCommandPollAt = 0;
}  // namespace

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== B-RMS BOOT ===");
    beginHeaterOutput();

    deviceMode = beginNetwork();
    if (deviceMode == DeviceMode::Provisioning) {
        Serial.println("Controller is waiting for initial configuration.");
        return;
    }

    Serial.println("Starting operational mode.");
    sensorsInit();
    networkWasConnected = true;
    lastRegistrationAttemptAt = millis();
    controllerRegistered = sendInit();
}

void loop() {
    handleNetwork();

    if (deviceMode != DeviceMode::Operational) {
        delay(5);
        return;
    }
    const bool networkConnected = isWiFiConnected();
    if (!networkConnected) {
        networkWasConnected = false;
        controllerRegistered = false;
        delay(25);
        return;
    }

    const uint32_t now = millis();
    if (now - lastCommandPollAt >= COMMAND_POLL_INTERVAL_MS) {
        lastCommandPollAt = now;
        if (pollControllerCommands()) {
            stopHeaterOutput();
            Serial.println("B-RMS requested Wi-Fi setup.");
            deviceMode = DeviceMode::Provisioning;
            controllerRegistered = false;
            enterWiFiSetup();
            return;
        }
    }
    if (!networkWasConnected) {
        networkWasConnected = true;
        lastRegistrationAttemptAt = now - REGISTRATION_RETRY_MS;
        Serial.println("Wi-Fi restored; registering controller again.");
    }
    if (!controllerRegistered) {
        if (now - lastRegistrationAttemptAt >= REGISTRATION_RETRY_MS) {
            lastRegistrationAttemptAt = now;
            controllerRegistered = sendInit();
        }
        delay(10);
        return;
    }

    if (now - lastTelemetryAt < TELEMETRY_INTERVAL_MS) {
        delay(5);
        return;
    }
    lastTelemetryAt = now;

    const bool sensorsValid = readSensors();
    updateHeaterTemperature(sensorsValid, lastTemp);
    if (!sensorsValid) {
        Serial.println("Skipping telemetry: sensor read failed.");
        return;
    }

    const String payload = buildPayload();
    Serial.println(payload);
    if (!sendTelemetry(payload)) {
        controllerRegistered = false;
        lastRegistrationAttemptAt = millis();
    }

}
