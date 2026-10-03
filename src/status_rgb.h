#pragma once

#include <Arduino.h>

void beginStatusRgb();
void setStatusRgbReady(bool ready);
void setStatusRgbSensorValid(bool valid);
void setStatusRgbBrewState(const char *status, bool overheat);
