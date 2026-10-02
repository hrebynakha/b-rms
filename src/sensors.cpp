#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>
#include <Wire.h>

#include "sensors.h"

#define ONE_WIRE_BUS 4
#ifndef INA226_ADDRESS
#define INA226_ADDRESS 0x40
#endif
#ifndef INA226_SDA_PIN
#define INA226_SDA_PIN 21
#endif
#ifndef INA226_SCL_PIN
#define INA226_SCL_PIN 22
#endif
#ifndef INA226_SHUNT_OHMS
#define INA226_SHUNT_OHMS 0.1f
#endif

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
DeviceAddress temperatureAddress;
bool temperatureFound = false;

namespace {
bool inaReady = false;
bool wireReady = false;
uint32_t lastInaRecoveryAt = 0;
constexpr uint16_t INA_CONFIG = 0x4127;
const char *inaError(uint8_t code) {
    switch (code) {
        case 0: return "OK";
        case 1: return "TX buffer full";
        case 2: return "address NACK: check power, wiring and address";
        case 3: return "data NACK";
        case 5: return "I2C timeout: check SDA/SCL and pull-ups";
        default: return "I2C bus error";
    }
}
bool beginInaBus() {
    wireReady = Wire.begin(INA226_SDA_PIN, INA226_SCL_PIN, 100000);
    Wire.setTimeOut(50);
    Serial.printf("INA226 I2C SDA=%d SCL=%d clock=100000 Hz address=0x%02X begin=%s\n",
                  INA226_SDA_PIN, INA226_SCL_PIN, INA226_ADDRESS, wireReady ? "OK" : "failed");
    return wireReady;
}
void scanInaBus() {
    if (!wireReady) return;
    Serial.printf("INA226 I2C scan: idle SDA=%d SCL=%d (both should be HIGH)\n",
                  digitalRead(INA226_SDA_PIN), digitalRead(INA226_SCL_PIN));
    unsigned found = 0, nacks = 0, timeouts = 0, errors = 0;
    for (uint8_t address = 0x08; address <= 0x77; ++address) {
        Wire.beginTransmission(address);
        const uint8_t error = Wire.endTransmission(true);
        if (error == 0) {
            Serial.printf("I2C ACK address: 0x%02X%s%s\n", address,
                          address >= 0x40 && address <= 0x4f ? " (INA226 candidate)" : "",
                          address == INA226_ADDRESS ? " (configured)" : "");
            ++found;
        } else if (error == 2) {
            ++nacks;
        } else if (error == 5) {
            ++timeouts;
        } else {
            ++errors;
        }
        // A stuck bus does not need another 111 timeout waits.
        if (error != 0 && error != 2) {
            Serial.printf("I2C scan aborted at 0x%02X: error=%u (%s)\n",
                          address, error, inaError(error));
            break;
        }
    }
    Serial.printf("I2C scan summary: ACK=%u address_NACK=%u timeout=%u other_error=%u\n",
                  found, nacks, timeouts, errors);
    if (!found) Serial.println("INA226: no I2C ACK; see scan errors and SDA/SCL levels above");
}
bool inaRead(uint8_t reg, uint16_t &value) {
    if (!wireReady) return false;
    Wire.beginTransmission(INA226_ADDRESS);
    Wire.write(reg);
    // INA226 retains its register pointer across STOP (TI Figure 6-7).
    // On this ESP32 core, false defers the write and hides its error until requestFrom.
    const uint8_t error = Wire.endTransmission(true);
    if (error != 0) {
        Serial.printf("INA226 read addr=0x%02X reg=0x%02X: error=%u (%s)\n",
                      INA226_ADDRESS, reg, error, inaError(error));
        return false;
    }
    const size_t received = Wire.requestFrom(uint8_t(INA226_ADDRESS), size_t(2), true);
    if (received != 2) {
        Serial.printf("INA226 read addr=0x%02X reg=0x%02X: received %u/2 bytes\n",
                      INA226_ADDRESS, reg, unsigned(received));
        while (Wire.available()) Wire.read();
        return false;
    }
    const uint16_t high = Wire.read();
    const uint16_t low = Wire.read();
    value = (high << 8) | low;
    return true;
}
bool inaBegin() {
    uint16_t manufacturer, device;
    if (!inaRead(0xfe, manufacturer) || !inaRead(0xff, device)) return false;
    Serial.printf("INA226 manufacturer=0x%04X device=0x%04X\n", manufacturer, device);
    if (manufacturer != 0x5449 || (device & 0xfff0) != 0x2260) {
        Serial.println("INA226: unexpected device ID; check module type and address");
        return false;
    }
    Wire.beginTransmission(INA226_ADDRESS);
    Wire.write(uint8_t(0));
    // One sample, 1.1 ms bus/shunt conversion, continuous bus + shunt.
    Wire.write(uint8_t(INA_CONFIG >> 8)); Wire.write(uint8_t(INA_CONFIG));
    const uint8_t error = Wire.endTransmission();
    if (error != 0) {
        Serial.printf("INA226 configure addr=0x%02X: error=%u (%s)\n",
                      INA226_ADDRESS, error, inaError(error));
        return false;
    }
    uint16_t config;
    if (!inaRead(0, config)) return false;
    Serial.printf("INA226 config=0x%04X expected=0x%04X: %s\n", config,
                  INA_CONFIG, config == INA_CONFIG ? "OK" : "mismatch");
    return config == INA_CONFIG;
}
void readPumpMonitor() {
    pumpVoltage = pumpCurrent = NAN;
    if (!inaReady) {
        // Recreate the ESP32 I2C driver after persistent failures, at most once per 30 s.
        if (millis() - lastInaRecoveryAt >= 30000) {
            lastInaRecoveryAt = millis();
            Serial.println("INA226: restarting I2C after persistent communication failure");
            Wire.end();
            wireReady = false;
            if (beginInaBus()) scanInaBus();
        }
        inaReady = wireReady && inaBegin();
        return; // Allow a conversion after restoring configuration.
    }
    uint16_t config;
    if (!inaRead(0, config)) { inaReady = false; return; }
    if (config != INA_CONFIG) {
        Serial.printf("INA226 configuration changed/reset: 0x%04X; reinitializing next cycle\n", config);
        inaReady = false;
        return;
    }
    uint16_t bus, shunt;
    if (!inaRead(2, bus)) { inaReady = false; return; }
    uint16_t status;
    if (!inaRead(6, status)) { inaReady = false; return; }
    const float volts = bus * 0.00125f;
    Serial.printf("INA226 bus_raw=0x%04X CVRF=%u bus=%.3f V\n",
                  bus, (status >> 3) & 1, volts);
    if (!(status & 0x0008)) {
        Serial.println("INA226: conversion not ready; retrying next cycle");
        return;
    }
    if (volts > 36) {
        Serial.println("INA226: bus exceeds 36 V input limit; measurement rejected");
        return;
    }
    pumpVoltage = volts; // VBUS to GND; wire VBUS to the pump positive terminal.
    if (!inaRead(1, shunt)) { inaReady = false; return; }
    const int16_t signedShunt = int16_t(shunt);
    Serial.printf("INA226 shunt_raw=0x%04X signed=%d shunt=%.3f mV R=%.4f ohm\n",
                  shunt, int(signedShunt), signedShunt * 0.0025f, float(INA226_SHUNT_OHMS));
    if (signedShunt == INT16_MIN || signedShunt == INT16_MAX) {
        Serial.println("INA226: shunt ADC at/outside +/-81.92 mV range; current unavailable");
        return;
    }
    if (!isfinite(float(INA226_SHUNT_OHMS)) || INA226_SHUNT_OHMS <= 0) {
        Serial.println("INA226: invalid INA226_SHUNT_OHMS; current unavailable");
        return;
    }
    pumpCurrent = signedShunt * 0.0000025f / INA226_SHUNT_OHMS;
    Serial.printf("INA226 measured: pump=%.3f V current=%.4f A\n", pumpVoltage, pumpCurrent);
}
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
float pumpVoltage = NAN;
float pumpCurrent = NAN;

void sensorsInit()
{
    lastInaRecoveryAt = millis();
    if (beginInaBus()) scanInaBus();
    inaReady = wireReady && inaBegin();
    Serial.printf("INA226 at 0x%02X: %s\n", INA226_ADDRESS, inaReady ? "found" : "not found; retrying");
    discoverTemperatureSensor();
}

bool readSensors()
{
    readPumpMonitor();
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
