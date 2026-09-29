import os
import random
import time
import requests



BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
MAC = "ESP32-002"


TEMPERATURE = 62.0
COOLING_TEMPERATURE = 24.0
VOLTAGE = 3.30

while True:

    TEMPERATURE += random.uniform(-0.3, 0.3)
    COOLING_TEMPERATURE += random.uniform(-0.2, 0.2)
    VOLTAGE += random.uniform(-0.01, 0.01)

    payload = {
        "mac_address": MAC,
        "metrics": {
            "mash_temperature_sensor": round(TEMPERATURE, 2),
            "cooling_temperature_sensor": round(COOLING_TEMPERATURE, 2),
            "input_voltage_sensor": round(VOLTAGE, 2),
        }
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/telemetry/",
        json=payload,
        timeout=5,
    )

    response.raise_for_status()
    print(response.json())

    time.sleep(3)
