#pragma once

#include <Arduino.h>

bool sendTelemetry(const String &payload);
bool sendInit();
bool pollControllerCommands();
bool sendButtonToggle(bool pump);
bool sendButtonStop();
String buildPayload();
