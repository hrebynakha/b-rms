#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

#include "sensors.h"

#define ONE_WIRE_BUS 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
DeviceAddress temperatureAddress;
bool temperatureFound = false;

namespace {
bool discoverTemperatureSensor()
{
    sensors.begin();
    temperatureFound = sensors.getAddress(temperatureAddress, 0);
    Serial.printf("DS18B20 GPIO%d: %u device(s), bus level %d, sensor %s.\n",
                  ONE_WIRE_BUS, sensors.getDeviceCount(), digitalRead(ONE_WIRE_BUS),
                  temperatureFound ? "found" : "not found");
    if (temperatureFound) {
        Serial.print("DS18B20 address: ");
        for (uint8_t byte : temperatureAddress) Serial.printf("%02X", byte);
        Serial.println();
        sensors.setResolution(temperatureAddress, 12);
        sensors.setWaitForConversion(false);
    }
    return temperatureFound;
}
}

float lastTemp = 0.0;
float voltage = 0.0;

void sensorsInit()
{
    discoverTemperatureSensor();
}

bool readSensors()
{
    if (!temperatureFound && !discoverTemperatureSensor()) {
        Serial.println("Sensor error: no DS18B20 on GPIO4; retrying discovery next cycle.");
        return false;
    }
    const auto conversion = sensors.requestTemperaturesByAddress(temperatureAddress);
    if (!conversion.result) {
        temperatureFound = false;
        Serial.println("Sensor error: DS18B20 not responding to conversion request.");
        return false;
    }
    // One conversion wait, including parasite-power mode; no double 750 ms delay.
    delay(750);

    float t = sensors.getTempC(temperatureAddress);

    if (!isfinite(t) || t == DEVICE_DISCONNECTED_C || t < -55 || t > 125)
    {
        temperatureFound = false;
        Serial.printf("Sensor error: DS18B20 read/CRC failed (%.2f C); rediscovering next cycle.\n", t);
        return false;
    }

    lastTemp = t;

    int raw = analogRead(34);
    delay(300);
    voltage = raw * (3.3 / 4095.0) * 2;

    return true;
}
