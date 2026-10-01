#pragma once

#include <Arduino.h>

bool sendTelemetry(const String &payload);
bool sendInit();
bool pollWiFiSetupCommand();
String buildPayload();
