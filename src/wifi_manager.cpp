#include <WiFi.h>

#include "wifi_manager.h"
#include "secrets.h"

const char* WIFI_SSID = CONFIG_WIFI_SSID;
const char* WIFI_PASS = CONFIG_WIFI_PASS;


void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    Serial.print("Connecting WiFi");

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\nWiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
}

bool isWiFiConnected() {
    return WiFi.status() == WL_CONNECTED;
}