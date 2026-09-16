#pragma once

#include <Arduino.h>

void saveConfig(
    const String &ssid,
    const String &password,
    const String &serverUrl);

bool loadConfig();
bool connectWifi();
void setupApiRoutes();
void setupStaticHtml();
void setupStaticFiles();
void setupPortal();

extern String wifiSsid;
extern String wifiPassword;
extern String serverUrl;
