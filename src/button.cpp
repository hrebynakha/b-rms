#include "button.h"
#include "buzzer.h"
#include "heater_output.h"

#ifndef BUTTON_INPUT_PIN
#define BUTTON_INPUT_PIN 32
#endif

namespace {
QueueHandle_t actions = nullptr;
void buttonTask(void *) {
    bool raw = false, pressed = false, held = false, reset = false;
    bool pumpSelected = false, clickPending = false, secondClick = false;
    uint32_t changedAt = millis(), pressedAt = 0, releasedAt = 0;
    for (;;) {
        const uint32_t now = millis();
        const bool sample = digitalRead(BUTTON_INPUT_PIN) == LOW;
        if (sample != raw) { raw = sample; changedAt = now; }
        if (raw != pressed && now - changedAt >= 40) {
            pressed = raw;
            if (pressed) {
                pressedAt = now;
                held = reset = false;
                secondClick = clickPending && now - releasedAt <= 300;
                // Commit an expired click before handling a new gesture.
                if (clickPending && !secondClick) {
                    const ButtonAction action = pumpSelected ? ButtonAction::Pump : ButtonAction::Heater;
                    if (xQueueSend(actions, &action, 0) != pdTRUE) beepBuzzer(3);
                    clickPending = false;
                }
            } else if (!held && now - pressedAt >= 3000) {
                held = true;
                clickPending = secondClick = false;
                const bool wifiReset = now - pressedAt >= 10000;
                inhibitHeaterOutput(wifiReset);
                const ButtonAction action = wifiReset ? ButtonAction::WiFiReset : ButtonAction::StopAll;
                xQueueOverwrite(actions, &action);
                if (wifiReset) beepBuzzer(3);
                else beepBuzzerState(false);
            } else if (!held) {
                if (secondClick) {
                    clickPending = false;
                    pumpSelected = !pumpSelected;
                    beepBuzzer(pumpSelected ? 2 : 1);
                    Serial.println(pumpSelected ? "Button mode: pump." : "Button mode: heater.");
                } else {
                    clickPending = true;
                    releasedAt = now;
                }
            }
        }
        if (pressed && !held && now - pressedAt >= 3000) {
            held = true;
            clickPending = secondClick = false;
            // Keep outputs off while the server stop is pending, including offline.
            inhibitHeaterOutput(false);
            const ButtonAction action = ButtonAction::StopAll;
            xQueueOverwrite(actions, &action);
            beepBuzzerState(false);
        }
        if (pressed && !reset && now - pressedAt >= 10000) {
            reset = true;
            inhibitHeaterOutput();
            const ButtonAction action = ButtonAction::WiFiReset;
            xQueueOverwrite(actions, &action);
            beepBuzzer(3);
        }
        // A second press cancels the single-click timer until it is released.
        if (clickPending && !pressed && !raw && now - releasedAt >= 300) {
            clickPending = false;
            const ButtonAction action = pumpSelected ? ButtonAction::Pump : ButtonAction::Heater;
            if (xQueueSend(actions, &action, 0) != pdTRUE) beepBuzzer(3);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
}

void beginButton() {
    pinMode(BUTTON_INPUT_PIN, INPUT_PULLUP);
    actions = xQueueCreate(1, sizeof(ButtonAction));
    if (actions && xTaskCreate(buttonTask, "button", 2048, nullptr, 1, nullptr) != pdPASS) {
        vQueueDelete(actions);
        actions = nullptr;
    }
    if (!actions) Serial.println("Button task failed.");
}

bool readButtonAction(ButtonAction &action) {
    return actions && xQueueReceive(actions, &action, 0) == pdTRUE;
}
