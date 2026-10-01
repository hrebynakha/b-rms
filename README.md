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
Run the complete backend test suite with `python manage.py test`.
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

### Manual temperature control (PID and time-proportional SSR output)

Equipment is grouped as **brewery → vessels**, with **one ESP controller per vessel**.
Use **Create brewery** / **Brewery settings** to edit the brewery name, location,
and description. **Vessel settings** edits the vessel name, working volume (20 L
by default), controller name, and brewery assignment. Existing controller identities
and telemetry remain intact. Multiple ESP controllers can belong to the same brewery;
each has independent manual controls. Moving a controller is blocked during active
manual control or an active brew session in either brewery.

The manual panel pulses blue within 1 °C below the target, green at the target,
and red at the overshoot threshold. Temperature changes use green/red/blue trend
badges. After at least five fresh intervals, estimated time uses a linear fit of
the last six to eleven readings and their actual timestamps. Cooling, flat readings,
stale data, and long gaps suppress the forecast. Start/apply resets the estimation
window. This is an approximate extrapolation of measured temperature, not a heater
power or water-volume model; working volume is saved for later physical calculations.
Recipe brew sessions still operate at brewery scope.

Open **Ручне керування** on a controller card. Set a target between 30 and 100 °C,
choose an overshoot threshold in °C or percent of the target, and press **Запустити**.
**Застосувати** saves adjustments; **Стоп** immediately sets the requested power to zero.
The ESP receives the updated request at its next command poll (every three seconds).

The control chain is **DS18B20 → local PID → 0–100% → time PWM → GPIO25
LOW/HIGH (0/~3.3 V) → SSR → heater OFF/ON**. The percentage determines the
fraction of time ON, rather than an analog control voltage. With the default
2,000 ms window, 25% means 500 ms ON and 1,500 ms OFF. GPIO4 remains the
temperature sensor; GPIO34 remains the existing input-voltage sensor.

PID runs on the ESP using fresh sensor readings and their elapsed time, with
derivative on measurement and integral anti-windup. The panel exposes Kp, Ki,
Kd and a window from 1,000 to 10,000 ms. Defaults are Kp=10, Ki=0.1, Kd=5;
these are initial values and require tuning for the actual vessel and heater.
Kp uses %/°C, Ki uses %/(°C·s), and Kd uses %·s/°C. Reaching the target can
leave a nonzero duty to maintain temperature. Start/apply resets PID state.

The live panel shows temperature, actual reported ON percentage, GPIO ON/OFF,
window timing, optional ADC voltage, and history. Missing reports remain empty.
The chart starts on Apply/Start; Refresh keeps only subsequent data. GPIO points
are telemetry snapshots every three seconds, so the chart cannot show every
edge of a two-second window. Connect a multimeter between GPIO25 and GND to
observe the low-voltage output; its display may average switching depending on
the meter. GPIO state reports confirm the programmed output, not SSR operation
or the voltage at the heater.

DS18B20 uses GPIO4. Serial logs show the discovered device count and ROM address;
failed reads invalidate the cached address and trigger discovery on the next
cycle, allowing recovery after reconnecting the sensor. Each reading waits once
for a 12-bit conversion. The SSR task runs on the other ESP32 core to avoid
preempting timing-sensitive OneWire reset pulses. Invalid readings still shut
down heating; recovery does not automatically rearm a latched heater fault.

To measure the actual output, wire a separate ADC1 feedback divider:

```text
GPIO25 ── 10 kΩ ──┬── 10 kΩ ── GND
                  │
                GPIO35
```

Then change `SSR_FEEDBACK_ENABLED=0` to `SSR_FEEDBACK_ENABLED=1` in `platformio.ini`
and rebuild/upload. Leave it disabled until the divider is wired; a floating ADC
does not provide a useful measurement. ESP samples the calibrated ADC every
250 ms and reports the latest instantaneous `measured_voltage` (multiplied by
two for the divider), without averaging across the PWM window.
The chart shows ON percentage, sampled GPIO state, and optional measured voltage.
Missing measurements stay empty rather than being inferred from duty.
ADC accuracy is limited; compare it with your meter. The ADC is for the low-voltage
control signal only, never the mains/SSR load terminals.

The output starts LOW. A separate FreeRTOS task switches the pin every 20 ms and keeps the output timeout working
while HTTP calls or sensor conversions block the main loop. Invalid/missing sensor
data, ten seconds without fresh commands or readings, Wi-Fi loss, setup mode, and
stop commands disable output. The local overheat threshold also disables the pin.
A fault is latched until an explicit new command revision arrives.
ESP reports the actual programmed window duty, ON/OFF state, timing, fault and command
revision separately from measured voltage. Stop requests reach the board on the next
successful poll; the UI waits for ESP confirmation rather than claiming immediate
physical shutdown. No connected heater or SSR is required for this bench test.

Before attaching a real SSR, verify its input can be driven by the board's 3.3 V
output and choose the required drive circuit from its datasheet. Add a 10 kΩ pull-down
from GPIO25 to GND if the external driver must remain LOW during reset/boot before
firmware initializes the pin.

Overshoot warnings continue after stopping. A +10 °C threshold at a 50 °C target
warns at 60 °C; a 10% threshold warns at 55 °C. Overheat, missing telemetry for
more than ten seconds, disabled controllers, and Wi-Fi reset stop the mode.
Restart explicitly after fresh readings return and the temperature is below the
warning threshold. Manual mode and an active brew session cannot run together.
Apply migrations and upload the updated firmware before testing. The protocol now
uses `output_mode: "time_pwm"` and sends PID parameters to the board, not a duty
calculated by the server. Migration 0014 pauses existing manual controls during
the upgrade; start again explicitly after updating the firmware.

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
