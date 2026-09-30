#include <ArduinoJson.h>
#include <LittleFS.h>
#include <WebServer.h>
#include <WiFi.h>

#include "portal.h"
#include "wifi_manager.h"

namespace {
constexpr char AP_SSID[] = "B-RMS-Setup";
constexpr char AP_PASSWORD[] = "brewmaster";
WebServer server(80);

void sendJson(int status, const String &body) {
    server.send(status, "application/json", body);
}
}  // namespace

void startProvisioningPortal() {
    WiFi.mode(WIFI_AP);
    if (!WiFi.softAP(AP_SSID, AP_PASSWORD)) {
        Serial.println("Failed to start provisioning access point.");
        return;
    }

    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS mount failed; provisioning page is unavailable.");
    }

    server.on("/", HTTP_GET, []() {
        File portal = LittleFS.open("/index.html", "r");
        if (!portal) {
            server.send(500, "text/plain", "Portal file is missing. Upload the LittleFS image.");
            return;
        }
        server.streamFile(portal, "text/html; charset=utf-8");
        portal.close();
    });
    server.on("/api/config", HTTP_POST, []() {
        if (!server.hasArg("plain")) {
            sendJson(400, "{\"error\":\"Request body is required\"}");
            return;
        }

        JsonDocument document;
        const DeserializationError error = deserializeJson(document, server.arg("plain"));
        if (error) {
            sendJson(400, "{\"error\":\"Invalid JSON\"}");
            return;
        }

        const String ssid = document["ssid"] | "";
        const String password = document["password"] | "";
        const String serverUrl = document["server_url"] | "";
        if (ssid.isEmpty() || serverUrl.isEmpty() ||
            !(serverUrl.startsWith("http://") || serverUrl.startsWith("https://"))) {
            sendJson(422, "{\"error\":\"SSID and a valid server URL are required\"}");
            return;
        }

        saveDeviceConfig(ssid, password, serverUrl);
        sendJson(200, "{\"success\":true}");
        delay(500);
        ESP.restart();
    });
    server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
    server.begin();

    Serial.println("Provisioning mode started.");
    Serial.printf("Connect to '%s' and open http://%s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
}

void handleProvisioningPortal() {
    server.handleClient();
}
