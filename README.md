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
