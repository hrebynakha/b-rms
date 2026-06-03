#include <OneWire.h>
#include <DallasTemperature.h>

#include "sensors.h"

#define ONE_WIRE_BUS 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

float lastTemp = 0.0;
float voltage = 0.0;



void sensorsInit() {
    sensors.begin();
}


bool readSensors() {
    sensors.requestTemperatures();
    delay(750);

    float t = sensors.getTempCByIndex(0);


    if (t == -127.0) {
        Serial.println("Sensor error");
        return false;
    }

    lastTemp = t;

    int raw = analogRead(34);
    delay(300);
    voltage = raw * (3.3 / 4095.0) * 2;

    return true;
}

