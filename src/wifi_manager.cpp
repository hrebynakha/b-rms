#include <Preferences.h>
#include <WiFi.h>

#include "portal.h"
#include "wifi_manager.h"

namespace {
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;
constexpr uint32_t WIFI_RECONNECT_INTERVAL_MS = 10000;

DeviceConfig config;
DeviceMode currentMode = DeviceMode::Provisioning;
uint32_t lastReconnectAttempt = 0;

String normalizeServerUrl(String url) {
    url.trim();
    while (url.endsWith("/")) {
        url.remove(url.length() - 1);
    }
    return url;
}

bool loadDeviceConfig() {
    Preferences preferences;
    preferences.begin("b-rms", true);
    config.wifiSsid = preferences.getString("ssid", "");
    config.wifiPassword = preferences.getString("pass", "");
    config.serverUrl = normalizeServerUrl(preferences.getString("server", ""));
    preferences.end();
    return !config.wifiSsid.isEmpty() && !config.serverUrl.isEmpty();
}

bool connectStation(uint32_t timeoutMs) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(false);
    WiFi.begin(config.wifiSsid.c_str(), config.wifiPassword.c_str());

    Serial.printf("Connecting to Wi-Fi '%s'", config.wifiSsid.c_str());
    const uint32_t startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < timeoutMs) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("Wi-Fi connection failed; opening provisioning portal.");
        WiFi.disconnect(true);
        return false;
    }

    Serial.print("Wi-Fi connected, IP: ");
    Serial.println(WiFi.localIP());
    return true;
}
}  // namespace

DeviceMode beginNetwork() {
    if (loadDeviceConfig() && connectStation(WIFI_CONNECT_TIMEOUT_MS)) {
        currentMode = DeviceMode::Operational;
        return currentMode;
    }

    currentMode = DeviceMode::Provisioning;
    startProvisioningPortal();
    return currentMode;
}

void handleNetwork() {
    if (currentMode == DeviceMode::Provisioning) {
        handleProvisioningPortal();
        return;
    }
    if (WiFi.status() == WL_CONNECTED) {
        return;
    }

    const uint32_t now = millis();
    if (now - lastReconnectAttempt >= WIFI_RECONNECT_INTERVAL_MS) {
        lastReconnectAttempt = now;
        Serial.println("Wi-Fi disconnected; reconnecting...");
        WiFi.reconnect();
    }
}

bool isWiFiConnected() {
    return currentMode == DeviceMode::Operational && WiFi.status() == WL_CONNECTED;
}

bool hasStoredConfig() {
    return !config.wifiSsid.isEmpty() && !config.serverUrl.isEmpty();
}

const DeviceConfig &getDeviceConfig() {
    return config;
}

void saveDeviceConfig(const String &ssid, const String &password, const String &serverUrl) {
    Preferences preferences;
    preferences.begin("b-rms", false);
    preferences.putString("ssid", ssid);
    preferences.putString("pass", password);
    preferences.putString("server", normalizeServerUrl(serverUrl));
    preferences.end();
}

void clearDeviceConfig() {
    Preferences preferences;
    preferences.begin("b-rms", false);
    preferences.clear();
    preferences.end();
}

void enterWiFiSetup() {
    clearDeviceConfig();
    config = DeviceConfig{};
    currentMode = DeviceMode::Provisioning;
    WiFi.setAutoReconnect(false);
    WiFi.disconnect(true);
    startProvisioningPortal();
}
