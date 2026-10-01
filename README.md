# 🍺 B-RMS — Brewery Remote Management System

<div align="center">

### Smart Brewery Automation Platform

Monitor, control, and automate your brewing process from anywhere.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Django](https://img.shields.io/badge/Django-5.x-green)
![ESP32](https://img.shields.io/badge/ESP32-IoT-red)
![MQTT](https://img.shields.io/badge/MQTT-Enabled-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

# 📖 Overview

**B-RMS (Brewery Remote Management System)** is an open-source brewery automation platform designed for homebrewers and small-scale breweries.

The system combines:

- 🌐 Web-based management dashboard
- 📡 ESP32 brewery controllers
- 📈 Real-time telemetry
- 🌡 Temperature monitoring
- 🔥 Heating element control (TEN)
- ⚙ Automated brewing workflows
- ☁ Remote monitoring and management

B-RMS allows brewers to monitor and control the entire brewing process from a browser, mobile phone, or tablet.

---

# ✨ Features

## 🌡 Brewing Control

- Temperature monitoring
- Multiple sensor support
- Heating element control
- Pump control
- Mash schedule automation
- Boiling stage management

## 📊 Telemetry & Monitoring

- Real-time sensor data
- Historical charts
- Temperature history
- Voltage monitoring
- Device health monitoring
- Online/offline status tracking

## 🏭 Brewery Management

- Multiple brewery support
- Multiple controller support
- Brewery registration
- Controller assignment
- Centralized management dashboard

## 🌐 Cloud Connectivity

- Secure API communication
- Remote configuration
- Live status updates
- Future MQTT support

## 🔧 Controller Management

- Firmware updates
- Wi-Fi provisioning
- Remote settings
- Device diagnostics

---

# 🏗 System Architecture

```text
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Django API  │
│   Backend   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │
└─────────────┘

       ▲
       │ HTTP / API
       │
┌──────┴──────┐
│    ESP32    │
│ Controller  │
└──────┬──────┘
       │
       ▼
 Sensors / Relays / Pumps / TEN
```

---

# 🛠 Technology Stack

## Backend

- Python 3.12+
- Django
- Django REST Framework
- PostgreSQL
- Nginx
- Docker

## Frontend

- HTML (Jinja templates)
- CSS
- JavaScript
- Bootstrap

## IoT

- ESP32
- PlatformIO
- Arduino Framework
- Wi-Fi
- HTTP API
- MQTT (planned)

---

# 📂 Repository Structure

```text
.
├── apps/               Django applications
├── config/             Django configuration
├── include/            ESP32 headers
├── lib/                ESP32 libraries
├── src/                ESP32 source code
├── scripts/            Utility scripts
├── static/             Static files
├── templates/          HTML templates
├── test/               Tests
├── platformio.ini      PlatformIO configuration
├── manage.py           Django entry point
├── requirements.txt    Python dependencies
└── README.md
```

---

# 🚀 Quick Start

## Clone Repository

```bash
git clone https://github.com/hrebynakha/b-rms.git

cd b-rms
```

---

# ⚙ Backend Setup

Create virtual environment:

```bash
python -m venv venv
```

Activate:

Linux:

```bash
source venv/bin/activate
```

Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run migrations:

```bash
python manage.py migrate
```

Compile EN/UK interface translations after editing `locale/uk/LC_MESSAGES/django.po`:

```bash
python scripts/compile_translations.py
```

Restart the Django server after recompiling to reload cached translations.
English source strings use Django `translate`/`gettext`; the Ukrainian catalog
also supplies dynamic chart labels, statuses, and errors. Generated `.mo` files
are ignored by Git and must be compiled on each installation.
The standalone ESP Wi-Fi setup page has its own EN/UK language selector and local
`trans` catalog, because it is served by the board without Django.

Create admin:

```bash
python manage.py createsuperuser
```

Run server:

```bash
python manage.py runserver
```

---

# 🐳 Docker Deployment

Pull nginx

```bash
docker pull nginx
```

Than, up the docker container

```bash

docker run --rm \
		-p 80:80 \
		-v <!project path> config/nginx.conf:/etc/nginx/nginx.conf:ro \
		--add-host=host.docker.internal:host-gateway \
		nginx
```

---

## Router setup

Fro now, to **ESP32** can communicate with Django Web server, u need provide in you private network special DNS

`beer.lan` , that will resolve the IP of current running Django Web server.

---

# 🔌 ESP32 Controller Setup

B-RMS controllers are built using **ESP32** and **PlatformIO**.

---

## 📥 Install PlatformIO

Install:

- Visual Studio Code
- PlatformIO Extension

---

## 📶 Wi-Fi Provisioning (In Progress)

The controller automatically creates a temporary Access Point when no Wi-Fi credentials are configured.

Example:

```text
B-RMS-Setup
```

Connect to:

```text
B-RMS-Setup
```

Then open:

```text
http://192.168.4.1
```

Configure:

- Wi-Fi SSID
- Wi-Fi Password
- Server URL
- Device Token

After saving, the device automatically reboots and connects to the brewery platform.

---

## ▶ Build Firmware

### Manual temperature control (real PWM output)

Open **Ручне керування** on a controller card. Set a target between 30 and 100 °C,
choose an overshoot threshold in °C or percent of the target, and press **Запустити**.
**Застосувати** saves adjustments; **Стоп** immediately sets the requested power to zero.
The ESP receives the updated request at its next command poll (every three seconds).

The live panel shows the latest and previous sensor temperatures, their difference,
requested power, calculated mean PWM voltage, optional measured ADC voltage, and history.
Control uses `power_percent = clamp((target - temperature) * 10, 0, 100)`:
at a 50 °C target, 45 °C requests 50% / 1.65 V and 50 °C requests zero.
ESP32 now drives **GPIO25** with real **1 kHz, 10-bit PWM**. The pin switches
between LOW and approximately 3.3 V; a DC multimeter shows its average (approximately
1.65 V at 50% duty). Connect the meter positive lead to GPIO25 and negative to GND.
This is PWM, not a DAC producing constant analog voltage. The exact voltage depends
on the board supply and meter. GPIO4 remains the temperature sensor; GPIO34 remains
the existing input-voltage sensor.

To measure the actual output, wire a separate ADC1 feedback divider:

```text
GPIO25 ── 10 kΩ ──┬── 10 kΩ ── GND
                  │
                GPIO35
```

Then change `SSR_FEEDBACK_ENABLED=0` to `SSR_FEEDBACK_ENABLED=1` in `platformio.ini`
and rebuild/upload. Leave it disabled until the divider is wired; a floating ADC
does not provide a useful measurement. ESP averages calibrated ADC samples and
reports `measured_voltage` (multiplied by two for the divider) in telemetry.
The purple chart line shows measured voltage; the orange line shows the requested
mean voltage. Missing measurements stay empty rather than being inferred from PWM.
ADC accuracy is limited; compare it with your meter. The ADC is for the low-voltage
control signal only, never the mains/SSR load terminals.

The PWM output starts LOW. A separate FreeRTOS task keeps the output timeout working
while HTTP calls or sensor conversions block the main loop. Invalid/missing sensor
data, ten seconds without fresh commands or readings, Wi-Fi loss, setup mode, and
stop commands disable output. ESP reports the actual programmed PWM duty and command
revision separately from measured voltage. Stop requests reach the board on the next
successful poll; the UI waits for ESP confirmation rather than claiming immediate
physical shutdown. No connected heater or SSR is required for this bench test.

Before attaching a real SSR, select its required drive circuit and switching mode
from its datasheet. A 1 kHz bench PWM signal is not a universal AC/zero-cross SSR
control mode; those commonly require time-proportional control. Add a 10 kΩ pull-down
from GPIO25 to GND if the external driver must remain LOW during reset/boot before
firmware initializes the pin.

Overshoot warnings continue after stopping. A +10 °C threshold at a 50 °C target
warns at 60 °C; a 10% threshold warns at 55 °C. Overheat, missing telemetry for
more than ten seconds, disabled controllers, and Wi-Fi reset stop the mode.
Restart explicitly after fresh readings return and the temperature is below the
warning threshold. Manual mode and an active brew session cannot run together.
Apply migrations and upload the updated firmware before testing.

The dashboard's **Reset Wi-Fi** button opens a confirmation modal. After confirmation,
the command remains queued until the ESP32 reads it from `GET /api/v1/commands/?mac_address=...`
and acknowledges it with `POST /api/v1/commands/` (`mac_address`, `command_id`).
Commands are polled every three seconds independently of sensor readings.
The controller clears saved Wi-Fi and server settings and opens `B-RMS-Setup`
(password `brewmaster`, setup page `http://192.168.4.1`). Configure the connection again
to resume telemetry. Offline controllers receive queued commands after reconnecting.
Apply backend migrations with `python manage.py migrate` before using this feature.

```bash
pio run
```

---

## ⬆ Upload Firmware

USB upload:

```bash
pio run --target upload
```

Monitor serial output:

```bash
pio device monitor
```

---

# 🌡 Supported Sensors

Current support:

- DS18B20
- NTC Thermistors

Planned:

- PT100
- PT1000
- MAX31865

---

# 🔥 Supported Outputs

- Solid State Relays (SSR)
- Mechanical Relays
- Heating Elements (TEN)
- Pumps
- Valves

---

# 📈 Telemetry

Controller periodically sends information from sensors:

```json
{
  "name": "ds18b20",
  "key": "mash_temperature_sensor",
  "kind": "temperature",
  "unit": "°C"
}
```

---

# 🔒 Security

For now it not planned because of all device will works in private network via http communication

---

# 🗺 Roadmap

## Phase 1

- [x] Brewery registration
- [x] Controller registration
- [x] Telemetry collection
- [x] Dashboard
- [ ] Wifi setup page

## Phase 2

- [ ] Heating automation
- [ ] Mash profiles
- [ ] Pump control
- [ ] Recipe management

## Phase 3

- [ ] MQTT communication
- [ ] OTA updates
- [ ] Mobile application
- [ ] Notification system

---

# 🤝 Contributing

Contributions are welcome.

1. Fork repository
2. Create feature branch
3. Commit changes
4. Open pull request

---

# 📜 License

Released under the MIT License.

---

<div align="center">

### 🍺 Brew Smarter. Brew Consistently. Brew Anywhere.

**B-RMS**

</div>
