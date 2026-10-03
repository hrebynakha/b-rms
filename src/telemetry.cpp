#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>

#include "sensors.h"
#include "buzzer.h"
#include "status_rgb.h"
#include "heater_output.h"
#include "telemetry.h"
#include "wifi_manager.h"

namespace {
constexpr char FIRMWARE_VERSION[] = "0.6.0";
constexpr uint32_t HTTP_TIMEOUT_MS = 5000;

String makeDeviceId() {
    char value[24];
    snprintf(value, sizeof(value), "esp32-%012llx", ESP.getEfuseMac());
    return String(value);
}

String deviceId = makeDeviceId();
bool buttonRevisionKnown = false;
uint32_t buttonRevision = 0;

String endpoint(const char *path) {
    return getDeviceConfig().serverUrl + path;
}

bool postJson(const String &url, const String &payload, String *responseBody = nullptr) {
    if (!isWiFiConnected()) {
        return false;
    }

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(url)) {
        Serial.printf("Unable to open HTTP connection to %s\n", url.c_str());
        return false;
    }
    http.addHeader("Content-Type", "application/json");
    const int statusCode = http.POST(payload);
    const String response = http.getString();
    http.end();

    if (statusCode < 200 || statusCode >= 300) {
        Serial.printf("POST %s failed: HTTP %d %s\n", url.c_str(), statusCode, response.c_str());
        return false;
    }
    if (responseBody) *responseBody = response;
    return true;
}

void addSensor(JsonArray &sensors, const char *name, const char *key, const char *kind, const char *unit) {
    JsonObject sensor = sensors.add<JsonObject>();
    sensor["name"] = name;
    sensor["key"] = key;
    sensor["kind"] = kind;
    sensor["unit"] = unit;
}
}  // namespace

bool sendInit() {
    JsonDocument document;
    document["mac_address"] = deviceId;
    document["firmware_version"] = FIRMWARE_VERSION;
    document["ip"] = WiFi.localIP().toString();

    JsonArray sensors = document["sensors"].to<JsonArray>();
    addSensor(sensors, "Mash temperature", "mash_temperature_sensor", "temperature", "°C");
    addSensor(sensors, "Input voltage", "input_voltage_sensor", "voltage", "V");
    addSensor(sensors, "Wi-Fi signal", "wifi_rssi_sensor", "signal", "dBm");
    addSensor(sensors, "Free heap", "free_heap_sensor", "memory", "bytes");
    addSensor(sensors, "Uptime", "uptime_sensor", "duration", "s");

    String payload;
    serializeJson(document, payload);
    const bool success = postJson(endpoint("/api/v1/bootstrap/"), payload);
    Serial.println(success ? "Controller registered with B-RMS." : "B-RMS registration failed.");
    return success;
}

bool sendButtonToggle(bool pump) {
    JsonDocument document;
    document["mac_address"] = deviceId;
    document["output"] = pump ? "pump" : "heater";
    String payload;
    serializeJson(document, payload);
    // Never retry a toggle automatically: a lost response may hide success.
    String response;
    if (!postJson(endpoint("/api/v1/button/"), payload, &response)) return false;
    JsonDocument state;
    if (deserializeJson(state, response) || state["output_mode"] != "direct") return false;
    buttonRevision = state["revision"] | 0U;
    buttonRevisionKnown = true;
    setDirectCommand(state["active"] == true, state["pump_on"] == true,
                     state["warning_temperature"] | 0.0f, buttonRevision);
    const HeaterOutputReport report = getHeaterOutputReport();
    const bool requestedOn = pump ? state["pump_on"] == true : state["active"] == true;
    if (report.fault || (pump ? report.pumpOn : report.enabled) != requestedOn) return false;
    beepBuzzerState(requestedOn);
    return true;
}

bool sendButtonStop() {
    JsonDocument document;
    document["mac_address"] = deviceId;
    document["output"] = "all";
    String payload, response;
    serializeJson(document, payload);
    if (!postJson(endpoint("/api/v1/button/"), payload, &response)) return false;
    JsonDocument state;
    if (deserializeJson(state, response) || !state["active"].is<bool>() ||
        !state["pump_on"].is<bool>() || state["active"].as<bool>() || state["pump_on"].as<bool>())
        return false;
    buttonRevision = state["revision"] | 0U;
    buttonRevisionKnown = true;
    stopHeaterOutput();
    releaseHeaterOutputInhibit();
    return true;
}

bool pollControllerCommands() {
    if (!isWiFiConnected()) return false;
    static String pendingCommandId;
    if (!pendingCommandId.isEmpty()) {
        JsonDocument acknowledgement;
        acknowledgement["mac_address"] = deviceId;
        acknowledgement["command_id"] = pendingCommandId;
        String payload;
        serializeJson(acknowledgement, payload);
        if (!postJson(endpoint("/api/v1/commands/"), payload)) return false;
        pendingCommandId = "";
        return true;
    }
    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(endpoint("/api/v1/commands/?mac_address=") + deviceId)) return false;
    const int statusCode = http.GET();
    const String response = http.getString();
    http.end();
    if (statusCode != 200) return false;
    JsonDocument document;
    if (deserializeJson(document, response)) return false;
    JsonObject manual = document["manual_control"].as<JsonObject>();
    // Establish a baseline after boot; an existing session is not a new start.
    static bool soundStateKnown = false;
    static uint32_t soundRevision = 0;
    static uint32_t soundSessionId = 0;
    static uint32_t soundStep = 0;
    const uint32_t nextRevision = manual["revision"] | 0U;
    JsonObject brew = document["brew_session"].as<JsonObject>();
    setStatusRgbBrewState(brew["status"] | "", manual["overheat"] == true);
    // Creating a draft is not a brew start; its ID becomes audible only on start.
    const uint32_t nextSessionId = brew["status"] == "pending" ? 0U : (brew["id"] | 0U);
    const uint32_t nextStep = brew["step_index"] | 0U;
    if (soundStateKnown) {
        if (nextRevision != soundRevision &&
            !(buttonRevisionKnown && nextRevision == buttonRevision)) beepBuzzer();
        if (nextSessionId && nextSessionId != soundSessionId) {
            beepBuzzer(2);
        } else if (nextSessionId && nextStep != soundStep) {
            beepBuzzer(3);
        }
    }
    soundStateKnown = true;
    soundRevision = nextRevision;
    soundSessionId = nextSessionId;
    soundStep = nextStep;
    if (!manual.isNull() && manual["output_mode"] == "direct") {
        setDirectCommand(manual["active"] == true, manual["pump_on"] == true,
                         manual["warning_temperature"] | 0.0f, manual["revision"] | 0U);
    } else if (!manual.isNull() && manual["output_mode"] == "time_pwm") {
        const uint32_t revision = manual["revision"] | 0U;
        const float target = manual["target_temperature"] | 0.0f;
        JsonObject gains = manual["pid"].as<JsonObject>();
        setHeaterCommand(manual["active"] == true, target, manual["warning_temperature"] | 0.0f,
                         gains["kp"] | NAN, gains["ki"] | NAN, gains["kd"] | NAN,
                         manual["window_ms"] | 0U, revision);
    } else {
        stopHeaterOutput();
    }
    for (JsonObject command : document["commands"].as<JsonArray>()) {
        const String commandId = command["id"] | "";
        if (command["type"] != "wifi_setup" || commandId.isEmpty()) continue;
        stopHeaterOutput();
        pendingCommandId = commandId;
        JsonDocument acknowledgement;
        acknowledgement["mac_address"] = deviceId;
        acknowledgement["command_id"] = commandId;
        String payload;
        serializeJson(acknowledgement, payload);
        // Keep polling until the server confirms receipt before disconnecting.
        if (postJson(endpoint("/api/v1/commands/"), payload)) {
            pendingCommandId = "";
            return true;
        }
    }
    return false;
}

String buildPayload() {
    JsonDocument document;
    document["mac_address"] = deviceId;
    JsonObject manual = document["manual_control"].to<JsonObject>();
    const HeaterOutputReport report = getHeaterOutputReport();
    manual["revision"] = report.revision;
    manual["power_percent"] = report.powerPercent;
    manual["output_mode"] = report.directMode ? "direct" : "time_pwm";
    manual["pump_on"] = report.pumpOn;
    if (isfinite(pumpVoltage)) {
        manual["pump_voltage"] = pumpVoltage;
    } else {
        manual["pump_voltage"] = nullptr;
    }
    if (isfinite(pumpCurrent)) {
        manual["pump_current"] = pumpCurrent;
    } else {
        manual["pump_current"] = nullptr;
    }
    manual["ssr_on"] = report.ssrOn;
    manual["window_ms"] = report.windowMs;
    manual["on_time_ms"] = report.onTimeMs;
    manual["enabled"] = report.enabled;
    manual["fault"] = report.fault;
    manual["feedback_enabled"] = report.feedbackEnabled;
    if (report.feedbackEnabled && isfinite(report.measuredVoltage)) {
        manual["measured_voltage"] = report.measuredVoltage;
    } else {
        manual["measured_voltage"] = nullptr;
    }
    JsonObject metrics = document["metrics"].to<JsonObject>();
    metrics["mash_temperature_sensor"] = round(lastTemp * 100) / 100.0;
    metrics["input_voltage_sensor"] = round(voltage * 100) / 100.0;
    metrics["wifi_rssi_sensor"] = WiFi.RSSI();
    metrics["free_heap_sensor"] = ESP.getFreeHeap();
    metrics["uptime_sensor"] = millis() / 1000;

    String output;
    serializeJson(document, output);
    return output;
}

bool sendTelemetry(const String &payload) {
    const bool success = postJson(endpoint("/api/v1/telemetry/"), payload);
    if (!success) {
        Serial.println("Telemetry delivery failed.");
    }
    return success;
}
