#include "buzzer.h"

#ifndef BUZZER_OUTPUT_PIN
#define BUZZER_OUTPUT_PIN 27
#endif
#ifndef BUZZER_ACTIVE
#define BUZZER_ACTIVE 0
#endif
#ifndef BUZZER_ACTIVE_HIGH
#define BUZZER_ACTIVE_HIGH 1
#endif
#ifndef BUZZER_FREQUENCY_HZ
#define BUZZER_FREQUENCY_HZ 3000
#endif
#ifndef BUZZER_PULSE_MS
#define BUZZER_PULSE_MS 150
#endif

static_assert(BUZZER_FREQUENCY_HZ > 0, "Buzzer frequency must be positive.");
static_assert(BUZZER_PULSE_MS > 0, "Buzzer pulse duration must be positive.");

namespace
{
    QueueHandle_t signals = nullptr;
    struct Signal { uint8_t pulses; uint32_t durationMs; };

    void writeBuzzer(bool on)
    {
        if (BUZZER_ACTIVE)
        {
            digitalWrite(BUZZER_OUTPUT_PIN, on == bool(BUZZER_ACTIVE_HIGH) ? HIGH : LOW);
        }
        else if (on)
        {
            tone(BUZZER_OUTPUT_PIN, BUZZER_FREQUENCY_HZ);
        }
        else
        {
            noTone(BUZZER_OUTPUT_PIN);
        }
    }

    void buzzerTask(void *)
    {
        Signal signal;
        for (;;)
        {
            if (xQueueReceive(signals, &signal, portMAX_DELAY) != pdTRUE)
                continue;
            Serial.printf("Buzzer: playing %u pulse(s).\n", signal.pulses);
            for (uint8_t i = 0; i < signal.pulses; ++i)
            {
                writeBuzzer(true);
                vTaskDelay(pdMS_TO_TICKS(signal.durationMs));
                writeBuzzer(false);
                vTaskDelay(pdMS_TO_TICKS(100));
            }
        }
    }
}

void beginBuzzer()
{
    Serial.printf("Buzzer: GPIO%d, %s, active %s, frequency %u Hz, pulse %u ms.\n",
                  BUZZER_OUTPUT_PIN, BUZZER_ACTIVE ? "active buzzer" : "passive buzzer",
                  BUZZER_ACTIVE_HIGH ? "HIGH" : "LOW",
                  unsigned(BUZZER_FREQUENCY_HZ), unsigned(BUZZER_PULSE_MS));
    pinMode(BUZZER_OUTPUT_PIN, OUTPUT);
    writeBuzzer(false);
    signals = xQueueCreate(8, sizeof(Signal));
    if (!signals)
    {
        Serial.println("Buzzer queue allocation failed.");
        return;
    }
    if (xTaskCreate(buzzerTask, "buzzer", 2048, nullptr, 1, nullptr) != pdPASS)
    {
        vQueueDelete(signals);
        signals = nullptr;
        Serial.println("Buzzer task failed.");
        return;
    }
    Serial.println("Buzzer initiated.");
    beepBuzzer(1);
}

void beepBuzzer(uint8_t pulses)
{
    if (signals && pulses >= 1 && pulses <= 3)
    {
        const Signal signal{pulses, BUZZER_PULSE_MS};
        if (xQueueSend(signals, &signal, 0) != pdTRUE)
            Serial.println("Buzzer: signal dropped, queue full.");
    }
}

void beepBuzzerState(bool on) {
    const Signal signal{1, on ? 100U : 500U};
    if (signals && xQueueSend(signals, &signal, 0) != pdTRUE)
        Serial.println("Buzzer: signal dropped, queue full.");
}
