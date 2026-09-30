#pragma once

#include <Arduino.h>

bool sendTelemetry(const String &payload);
bool sendInit();
String buildPayload();
