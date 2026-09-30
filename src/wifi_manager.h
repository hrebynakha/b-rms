#pragma once

#include <Arduino.h>

enum class DeviceMode {
    Provisioning,
    Operational,
};

struct DeviceConfig {
    String wifiSsid;
    String wifiPassword;
    String serverUrl;
};

DeviceMode beginNetwork();
void handleNetwork();
bool isWiFiConnected();
bool hasStoredConfig();
const DeviceConfig &getDeviceConfig();
void saveDeviceConfig(const String &ssid, const String &password, const String &serverUrl);
void clearDeviceConfig();
