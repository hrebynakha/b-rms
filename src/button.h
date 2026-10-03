#pragma once
#include <Arduino.h>

enum class ButtonAction : uint8_t { Heater, Pump, StopAll, WiFiReset };
void beginButton();
bool readButtonAction(ButtonAction &action);
