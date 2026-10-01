#include <WiFi.h>
#include <math.h>

#include "heater_output.h"

#ifndef SSR_OUTPUT_PIN
#define SSR_OUTPUT_PIN 25
#endif
#ifndef SSR_FEEDBACK_PIN
#define SSR_FEEDBACK_PIN 35
#endif
#ifndef SSR_FEEDBACK_ENABLED
#define SSR_FEEDBACK_ENABLED 0
#endif

namespace {
constexpr int PWM_CHANNEL = 0;
constexpr int PWM_FREQUENCY = 1000;
constexpr int PWM_BITS = 10;
constexpr int PWM_MAX = (1 << PWM_BITS) - 1;
constexpr uint32_t MAX_AGE_MS = 10000;
// Two equal 10 kOhm resistors divide output voltage by two before ADC1.
constexpr float FEEDBACK_DIVIDER_RATIO = 2.0f;
portMUX_TYPE outputMux = portMUX_INITIALIZER_UNLOCKED;
bool enabled = false;
bool sensorValid = false;
float sensorTemperature = NAN;
float targetTemperature = 0;
float requestedPower = 0;
uint32_t commandAt = 0;
uint32_t sensorAt = 0;
uint32_t revision = 0;
float appliedPower = 0;
float measuredVoltage = NAN;

void outputTask(void *) {
    uint32_t lastFeedbackAt = 0;
    for (;;) {
        const uint32_t now = millis();
        const bool connected = WiFi.status() == WL_CONNECTED;
        portENTER_CRITICAL(&outputMux);
        if (!connected || !sensorValid || now - commandAt >= MAX_AGE_MS ||
            now - sensorAt >= MAX_AGE_MS) enabled = false;
        const float power = enabled && sensorTemperature < targetTemperature ? requestedPower : 0;
        const uint32_t duty = lroundf(power * PWM_MAX / 100.0f);
        ledcWrite(PWM_CHANNEL, duty);
        appliedPower = duty * 100.0f / PWM_MAX;
        portEXIT_CRITICAL(&outputMux);
        if (SSR_FEEDBACK_ENABLED && now - lastFeedbackAt >= 250) {
            lastFeedbackAt = now;
            uint32_t sumMillivolts = 0;
            // Average across many PWM periods; vary spacing to avoid phase locking.
            for (int i = 0; i < 128; ++i) {
                sumMillivolts += analogReadMilliVolts(SSR_FEEDBACK_PIN);
                delayMicroseconds(137 + (i * 29) % 113);
            }
            const float voltage = sumMillivolts / 128000.0f * FEEDBACK_DIVIDER_RATIO;
            portENTER_CRITICAL(&outputMux);
            measuredVoltage = voltage;
            portEXIT_CRITICAL(&outputMux);
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
}  // namespace

void beginHeaterOutput() {
    pinMode(SSR_OUTPUT_PIN, OUTPUT);
    digitalWrite(SSR_OUTPUT_PIN, LOW);
    if (!ledcSetup(PWM_CHANNEL, PWM_FREQUENCY, PWM_BITS)) {
        Serial.println("SSR PWM initialization failed; output remains LOW.");
        return;
    }
    ledcAttachPin(SSR_OUTPUT_PIN, PWM_CHANNEL);
    ledcWrite(PWM_CHANNEL, 0);
    if (SSR_FEEDBACK_ENABLED) {
        pinMode(SSR_FEEDBACK_PIN, INPUT);
        analogSetPinAttenuation(SSR_FEEDBACK_PIN, ADC_11db);
    }
    if (xTaskCreate(outputTask, "heater-output", 4096, nullptr, 2, nullptr) != pdPASS) {
        Serial.println("SSR output task failed; output remains LOW.");
        ledcWrite(PWM_CHANNEL, 0);
    }
    Serial.printf("SSR PWM: GPIO%d, %d Hz; ADC feedback: %s (GPIO%d).\n",
                  SSR_OUTPUT_PIN, PWM_FREQUENCY, SSR_FEEDBACK_ENABLED ? "enabled" : "disabled", SSR_FEEDBACK_PIN);
}

void stopHeaterOutput() {
    portENTER_CRITICAL(&outputMux);
    enabled = false;
    requestedPower = 0;
    appliedPower = 0;
    ledcWrite(PWM_CHANNEL, 0);
    portEXIT_CRITICAL(&outputMux);
}

void updateHeaterTemperature(bool valid, float temperature) {
    portENTER_CRITICAL(&outputMux);
    sensorValid = valid && isfinite(temperature) && temperature >= -55 && temperature <= 125;
    sensorTemperature = temperature;
    sensorAt = millis();
    if (!sensorValid) {
        enabled = false;
        appliedPower = 0;
        ledcWrite(PWM_CHANNEL, 0);
    }
    portEXIT_CRITICAL(&outputMux);
}

void setHeaterCommand(bool active, float target, float power, uint32_t commandRevision) {
    portENTER_CRITICAL(&outputMux);
    revision = commandRevision;
    targetTemperature = target;
    commandAt = millis();
    enabled = active && isfinite(target) && target >= 30 && target <= 100 &&
              isfinite(power) && power >= 0 && power <= 100 && sensorValid;
    requestedPower = enabled ? power : 0;
    if (!enabled) {
        appliedPower = 0;
        ledcWrite(PWM_CHANNEL, 0);
    }
    portEXIT_CRITICAL(&outputMux);
}

HeaterOutputReport getHeaterOutputReport() {
    portENTER_CRITICAL(&outputMux);
    HeaterOutputReport report{revision, appliedPower, measuredVoltage, SSR_FEEDBACK_ENABLED != 0};
    portEXIT_CRITICAL(&outputMux);
    return report;
}
