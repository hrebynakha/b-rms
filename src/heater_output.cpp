#include <WiFi.h>
#include <math.h>
#include "heater_output.h"
#include "pid_control.h"
#ifndef SSR_OUTPUT_PIN
#define SSR_OUTPUT_PIN 25
#endif
#ifndef PUMP_OUTPUT_PIN
#define PUMP_OUTPUT_PIN 26
#endif
#ifndef PUMP_RELAY_ACTIVE_HIGH
#define PUMP_RELAY_ACTIVE_HIGH 1
#endif
#ifndef SSR_FEEDBACK_PIN
#define SSR_FEEDBACK_PIN 35
#endif
#ifndef SSR_FEEDBACK_ENABLED
#define SSR_FEEDBACK_ENABLED 0
#endif

namespace {
constexpr uint32_t MAX_AGE_MS = 10000;
portMUX_TYPE outputMux = portMUX_INITIALIZER_UNLOCKED;
HeatingPid pid;
bool enabled = false, sensorValid = false, faultLatched = false;
bool directMode = false, pumpOn = false;
bool inhibited = false;
bool permanentlyInhibited = false;
void writePump(bool on) { digitalWrite(PUMP_OUTPUT_PIN, on == bool(PUMP_RELAY_ACTIVE_HIGH) ? HIGH : LOW); }
bool outputOn = false, resetPending = true, taskReady = false;
float sensorTemperature = NAN, targetTemperature = 50, overheatTemperature = 60;
float kp = 10, ki = .1f, kd = 5;
uint32_t commandAt = 0, sensorAt = 0, revision = 0, faultRevision = 0;
uint32_t sensorSequence = 0, consumedSequence = 0;
uint32_t windowMs = 2000, windowAt = 0, onTimeMs = 0;
float windowPower = 0, measuredVoltage = NAN;

void off() {
    pumpOn = false;
    writePump(false);
    enabled = false;
    outputOn = false;
    windowPower = 0;
    onTimeMs = 0;
    resetPending = true;
    digitalWrite(SSR_OUTPUT_PIN, LOW);
}
void trip() { faultLatched = true; faultRevision = revision; off(); }

void outputTask(void *) {
    uint32_t lastFeedbackAt = 0;
    for (;;) {
        const uint32_t now = millis();
        const bool connected = WiFi.status() == WL_CONNECTED;
        portENTER_CRITICAL(&outputMux);
        if ((enabled || pumpOn) && (!connected || !sensorValid || now - commandAt >= MAX_AGE_MS ||
                        now - sensorAt >= MAX_AGE_MS || (enabled && sensorTemperature >= overheatTemperature))) trip();
        if (enabled && directMode) {
            windowPower = 100;
            onTimeMs = windowMs;
            outputOn = true;
            digitalWrite(SSR_OUTPUT_PIN, HIGH);
        } else if (enabled) {
            const bool reset = resetPending;
            if (reset) { pid.reset(); windowAt = now; resetPending = false; }
            if (reset || sensorSequence != consumedSequence) {
                pid.update(targetTemperature, sensorTemperature, sensorAt, kp, ki, kd);
                consumedSequence = sensorSequence;
            }
            const uint32_t elapsed = now - windowAt;
            if (reset || elapsed >= windowMs) {
                if (!reset) windowAt += (elapsed / windowMs) * windowMs;
                // Freeze duty for this window; apply new PID results at its boundary.
                windowPower = pid.value();
                onTimeMs = lroundf(windowPower * windowMs / 100.0f);
            }
            if (pid.value() <= 0) { windowPower = 0; onTimeMs = 0; }
            outputOn = (now - windowAt) < onTimeMs;
            digitalWrite(SSR_OUTPUT_PIN, outputOn ? HIGH : LOW);
        }
        portEXIT_CRITICAL(&outputMux);
        if (SSR_FEEDBACK_ENABLED && now - lastFeedbackAt >= 250) {
            lastFeedbackAt = now;
            // Instantaneous control level: no averaging across the time-PWM window.
            const float voltage = analogReadMilliVolts(SSR_FEEDBACK_PIN) / 1000.0f * 2.0f;
            portENTER_CRITICAL(&outputMux);
            measuredVoltage = voltage;
            portEXIT_CRITICAL(&outputMux);
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
}

void beginHeaterOutput() {
    writePump(false);
    pinMode(PUMP_OUTPUT_PIN, OUTPUT);
    writePump(false);
    pinMode(SSR_OUTPUT_PIN, OUTPUT);
    digitalWrite(SSR_OUTPUT_PIN, LOW);
    if (SSR_FEEDBACK_ENABLED) {
        pinMode(SSR_FEEDBACK_PIN, INPUT);
        analogSetPinAttenuation(SSR_FEEDBACK_PIN, ADC_11db);
    }
    // OneWire reset pulses contain timing-sensitive intervals outside its bit-level
    // critical sections. Keep this periodic higher-priority task off the loop core.
#if CONFIG_FREERTOS_UNICORE
    taskReady = xTaskCreate(outputTask, "heater-output", 4096, nullptr, 1, nullptr) == pdPASS;
#else
    taskReady = xTaskCreatePinnedToCore(outputTask, "heater-output", 4096, nullptr, 2,
                                      nullptr, ARDUINO_RUNNING_CORE == 1 ? 0 : 1) == pdPASS;
#endif
    if (!taskReady) Serial.println("SSR task failed; output remains LOW.");
    Serial.printf("PID time PWM: GPIO%d, default window %u ms; ADC GPIO%d: %s.\n",
                  SSR_OUTPUT_PIN, windowMs, SSR_FEEDBACK_PIN, SSR_FEEDBACK_ENABLED ? "enabled" : "disabled");
}

void stopHeaterOutput() {
    portENTER_CRITICAL(&outputMux);
    off();
    portEXIT_CRITICAL(&outputMux);
}

void inhibitHeaterOutput(bool permanent) {
    portENTER_CRITICAL(&outputMux);
    inhibited = true;
    permanentlyInhibited = permanentlyInhibited || permanent;
    off();
    portEXIT_CRITICAL(&outputMux);
}

void releaseHeaterOutputInhibit() {
    portENTER_CRITICAL(&outputMux);
    if (!permanentlyInhibited) inhibited = false;
    portEXIT_CRITICAL(&outputMux);
}

void updateHeaterTemperature(bool valid, float temperature) {
    portENTER_CRITICAL(&outputMux);
    sensorValid = valid && isfinite(temperature) && temperature >= -55 && temperature <= 125;
    sensorTemperature = temperature;
    sensorAt = millis();
    sensorSequence++;
    if (enabled && (!sensorValid || temperature >= overheatTemperature)) trip();
    portEXIT_CRITICAL(&outputMux);
}

void setHeaterCommand(bool active, float target, float overheat, float newKp, float newKi,
                      float newKd, uint32_t newWindowMs, uint32_t commandRevision) {
    portENTER_CRITICAL(&outputMux);
    if (directMode) off();
    directMode = false;
    const bool changed = revision != commandRevision || target != targetTemperature ||
        newKp != kp || newKi != ki || newKd != kd || newWindowMs != windowMs || overheat != overheatTemperature;
    revision = commandRevision;
    commandAt = millis();
    const bool valid = taskReady && !inhibited && isfinite(target) && target >= 30 && target <= 100 &&
        isfinite(overheat) && overheat > target && overheat <= 150 &&
        isfinite(newKp) && newKp >= 0 && newKp <= 100 &&
        isfinite(newKi) && newKi >= 0 && newKi <= 10 &&
        isfinite(newKd) && newKd >= 0 && newKd <= 1000 && newWindowMs >= 1000 && newWindowMs <= 10000;
    if (!active || !valid || (faultLatched && faultRevision == revision)) {
        off();
    } else {
        if (changed || !enabled) off();
        targetTemperature = target;
        overheatTemperature = overheat;
        kp = newKp; ki = newKi; kd = newKd; windowMs = newWindowMs;
        enabled = true;
        faultLatched = false;
    }
    portEXIT_CRITICAL(&outputMux);
}

HeaterOutputReport getHeaterOutputReport() {
    portENTER_CRITICAL(&outputMux);
    HeaterOutputReport report{revision, windowPower, measuredVoltage, SSR_FEEDBACK_ENABLED != 0,
                             outputOn, windowMs, onTimeMs, enabled, faultLatched, directMode, pumpOn};
    portEXIT_CRITICAL(&outputMux);
    return report;
}

void setDirectCommand(bool heaterOn, bool requestedPumpOn, float overheat, uint32_t commandRevision) {
    portENTER_CRITICAL(&outputMux);
    const bool blocked = faultLatched && faultRevision == commandRevision;
    if (!directMode || revision != commandRevision) off();
    directMode = true;
    revision = commandRevision;
    commandAt = millis();
    if (!taskReady || inhibited || blocked || !isfinite(overheat) || overheat <= 0 || overheat > 150) {
        off();
    } else {
        faultLatched = false;
        overheatTemperature = overheat;
        enabled = heaterOn;
        pumpOn = requestedPumpOn;
        writePump(pumpOn);
        if (!enabled) {
            outputOn = false;
            windowPower = 0;
            onTimeMs = 0;
            digitalWrite(SSR_OUTPUT_PIN, LOW);
        }
    }
    portEXIT_CRITICAL(&outputMux);
}
