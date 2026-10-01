#pragma once

#include <Arduino.h>

struct HeaterOutputReport {
    uint32_t revision;
    float powerPercent;
    float measuredVoltage;
    bool feedbackEnabled;
};

void beginHeaterOutput();
void stopHeaterOutput();
void updateHeaterTemperature(bool valid, float temperature);
void setHeaterCommand(bool active, float target, float power, uint32_t revision);
HeaterOutputReport getHeaterOutputReport();
