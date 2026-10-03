#include "status_rgb.h"

#include "heater_output.h"
#include "wifi_manager.h"

#ifndef RGB_RED_PIN
#define RGB_RED_PIN 16
#endif
#ifndef RGB_GREEN_PIN
#define RGB_GREEN_PIN 17
#endif
#ifndef RGB_BLUE_PIN
#define RGB_BLUE_PIN 18
#endif
#ifndef RGB_ACTIVE_HIGH
#define RGB_ACTIVE_HIGH 1
#endif

namespace {
enum class BrewState { Idle, Pending, Running, Paused, Failed };
portMUX_TYPE rgbMux = portMUX_INITIALIZER_UNLOCKED;
bool ready = false, sensorValid = true, serverOverheat = false, commandKnown = false;
uint32_t commandAt = 0, readyAt = 0;
BrewState brewState = BrewState::Idle;

void writeChannel(int pin, bool on) {
    digitalWrite(pin, on == bool(RGB_ACTIVE_HIGH) ? HIGH : LOW);
}

void writeGreen(uint8_t brightness) {
    analogWrite(RGB_GREEN_PIN, RGB_ACTIVE_HIGH ? brightness : 255 - brightness);
}

void rgbTask(void *) {
    uint8_t previous = 255;
    uint32_t phaseAt = millis();
    for (;;) {
        const uint32_t now = millis();
        portENTER_CRITICAL(&rgbMux);
        const bool initialized = ready;
        const bool sensorError = !sensorValid;
        const bool overheat = serverOverheat;
        const bool stale = now - (commandKnown ? commandAt : readyAt) >= 10000;
        const bool known = commandKnown;
        const BrewState brew = brewState;
        portEXIT_CRITICAL(&rgbMux);
        const bool brewing = brew == BrewState::Running || brew == BrewState::Paused;
        const bool error = sensorError || overheat || getHeaterOutputReport().fault ||
                           (initialized && (!isWiFiConnected() || stale));
        // Red errors take priority over setup, pause and normal operation.
        const bool red = error || brew == BrewState::Failed;
        const bool yellow = !red && (!initialized || !known || brew == BrewState::Paused);
        const bool blue = !red && !yellow && (brew == BrewState::Pending || brew == BrewState::Running);
        const bool blink = red ? (brewing || brew == BrewState::Failed) :
                           yellow ? (!initialized || !known) : brew == BrewState::Running;
        const uint8_t mode = (red ? 1 : yellow ? 2 : blue ? 3 : 4) + (blink ? 4 : 0);
        if (mode != previous) { previous = mode; phaseAt = now; }
        const bool on = !blink || ((now - phaseAt) / 500) % 2 == 0;
        writeChannel(RGB_RED_PIN, on && (red || yellow));
        // A pause needs attention: use a redder orange than the startup yellow.
        const uint8_t green = yellow && initialized && known ? 48 : 255;
        writeGreen(on && !red && !blue ? green : 0);
        writeChannel(RGB_BLUE_PIN, on && blue);
        vTaskDelay(pdMS_TO_TICKS(25));
    }
}
}  // namespace

void beginStatusRgb() {
    for (const int pin : {RGB_RED_PIN, RGB_GREEN_PIN, RGB_BLUE_PIN}) {
        writeChannel(pin, false);
        pinMode(pin, OUTPUT);
    }
    writeChannel(RGB_RED_PIN, true);
    writeChannel(RGB_GREEN_PIN, true);
    if (xTaskCreate(rgbTask, "status-rgb", 2048, nullptr, 1, nullptr) != pdPASS) {
        writeChannel(RGB_GREEN_PIN, false);
        Serial.println("RGB status task failed.");
    }
}

void setStatusRgbReady(bool value) {
    portENTER_CRITICAL(&rgbMux);
    if (value && !ready) readyAt = millis();
    ready = value;
    if (!value) { commandKnown = false; brewState = BrewState::Idle; serverOverheat = false; }
    portEXIT_CRITICAL(&rgbMux);
}

void setStatusRgbSensorValid(bool value) {
    portENTER_CRITICAL(&rgbMux);
    sensorValid = value;
    portEXIT_CRITICAL(&rgbMux);
}

void setStatusRgbBrewState(const char *status, bool overheat) {
    BrewState next = BrewState::Idle;
    if (!strcmp(status, "pending")) next = BrewState::Pending;
    else if (!strcmp(status, "running") || !strcmp(status, "heating")) next = BrewState::Running;
    else if (!strcmp(status, "paused") || !strcmp(status, "waiting_temperature")) next = BrewState::Paused;
    else if (!strcmp(status, "failed")) next = BrewState::Failed;
    portENTER_CRITICAL(&rgbMux);
    brewState = next;
    serverOverheat = overheat;
    commandKnown = true;
    commandAt = millis();
    portEXIT_CRITICAL(&rgbMux);
}
