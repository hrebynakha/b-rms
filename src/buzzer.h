#pragma once

#include <Arduino.h>

void beginBuzzer();
void beepBuzzer(uint8_t pulses = 1);
void beepBuzzerState(bool on);
