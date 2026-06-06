#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <ArduinoJson.h>

AsyncWebServer server(80);
Preferences prefs;

#define AP_SSID "B-RMS-Portal"
#define AP_PASSWORD "brewmaster"

String wifiSsid;
String wifiPassword;
String serverUrl;

void saveConfig(
    const String &ssid,
    const String &password,
    const String &serverUrl)
{
    prefs.begin("b-rms", false);

    prefs.putString("ssid", ssid);
    prefs.putString("pass", password);
    prefs.putString("server", serverUrl);

    prefs.end();
}

bool loadConfig()
{
    prefs.begin("b-rms", true);

    wifiSsid = prefs.getString("ssid", "");
    wifiPassword = prefs.getString("pass", "");
    serverUrl = prefs.getString("server", "");

    prefs.end();

    return !wifiSsid.isEmpty();
}

bool connectWifi()
{
    if (wifiSsid.isEmpty())
        return false;

    WiFi.mode(WIFI_STA);

    WiFi.begin(
        wifiSsid.c_str(),
        wifiPassword.c_str());

    Serial.print("Connecting");

    for (int i = 0; i < 20; i++)
    {
        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.println();
            Serial.println("Connected");

            Serial.println(WiFi.localIP());

            return true;
        }

        Serial.print(".");
        delay(500);
    }

    Serial.println();
    Serial.println("Connection failed");

    return false;
}

void setupApiRoutes()
{
    server.on(
        "/api/config",
        HTTP_POST,
        [](AsyncWebServerRequest *request) {},
        NULL,
        [](AsyncWebServerRequest *request,
           uint8_t *data,
           size_t len,
           size_t index,
           size_t total)
        {
            JsonDocument doc;

            auto err = deserializeJson(doc, data);

            if (err)
            {
                request->send(
                    400,
                    "application/json",
                    "{\"success\":false}");

                return;
            }

            String ssid =
                doc["ssid"] | "";

            String password =
                doc["password"] | "";

            String serverUrl =
                doc["server_url"] | "";

            saveConfig(
                ssid,
                password,
                serverUrl);

            request->send(
                200,
                "application/json",
                "{\"success\":true}");

            delay(1000);

            ESP.restart();
        });
}

void setupStaticHtml()
{
    server.serveStatic(
              "/",
              LittleFS,
              "/")
        .setDefaultFile("index.html");
}

void setupStaticFiles()
{
    Serial.println("Starting setup portal");

    WiFi.mode(WIFI_AP);

    WiFi.softAP(
        AP_SSID,
        AP_PASSWORD);

    Serial.println(
        WiFi.softAPIP());

    if (!LittleFS.begin(true))
    {
        Serial.println(
            "LittleFS mount failed");

        return;
    }

    setupStaticHtml();
    setupApiRoutes();

    server.begin();

    Serial.println(
        "Portal ready");
}

void setupPortal()
{
    bool configExists =
        loadConfig();

    if (configExists)
    {
        if (connectWifi())
        {
            Serial.println(
                "Starting normal B-RMS mode");

            return;
        }
    }

    startProvisioningPortal();
}