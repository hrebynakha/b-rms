#pragma once

#include <Arduino.h>

void sendTelemetry(const String &payload);
bool sendInit();
String buildPayload();