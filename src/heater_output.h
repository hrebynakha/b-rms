#pragma once

#include <Arduino.h>

struct HeaterOutputReport {
    uint32_t revision;
    float powerPercent;
    float measuredVoltage;
    bool feedbackEnabled;
    bool ssrOn;
    uint32_t windowMs;
    uint32_t onTimeMs;
    bool enabled;
    bool fault;
    bool directMode;
    bool pumpOn;
};

void beginHeaterOutput();
void stopHeaterOutput();
void inhibitHeaterOutput(bool permanent = true);
void releaseHeaterOutputInhibit();
void updateHeaterTemperature(bool valid, float temperature);
void setHeaterCommand(bool active, float target, float overheat, float kp, float ki,
                      float kd, uint32_t windowMs, uint32_t revision);
HeaterOutputReport getHeaterOutputReport();
void setDirectCommand(bool heaterOn, bool pumpOn, float overheat, uint32_t revision);
