import os
import requests

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


payload = {
    "mac_address": "ESP32-002",
    "firmware_version": "0.1.1",
    "sensors": [
        {
            "key": "mash_temperature_sensor",
            "kind": "temperature",
            "unit": "°C",
        },
        {
            "key": "input_voltage_sensor",
            "kind": "voltage",
            "unit": "V",
        }
    ]
}

r = requests.post(
    f"{BASE_URL}/api/v1/bootstrap/",
    json=payload,
    timeout=5,
)

print(r.status_code)
print(r.text)
