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

## Ручне керування ТЕНом і помпою

### Фізична кнопка

Підключіть кнопку між GPIO32 і GND (внутрішній pull-up).
Пін задається через `BUTTON_INPUT_PIN` у `platformio.ini`.

- Один клік: увімкнення/вимкнення вибраного виходу після паузи 300 мс.
- Подвійний клік: вибір ТЕНа (1 біп) або помпи (2 біпи), без зміни виходів.
  Після запуску вибраний ТЕН; друге натискання має початися протягом 300 мс.
- Утримання 3 секунди: негайне локальне вимкнення обох виходів.
- Подальше утримання до 10 секунд: 3 біпи, скидання Wi-Fi та адреси
  сервера і відкриття provisioning `B-RMS-Setup`.

Відпускання після довгого утримання не виконує кліку. Увімкнення підтверджується
коротким сигналом 100 мс, вимкнення — довшим 500 мс. Кнопка зчитується окремою задачею
з усуненням брязкоту (40 мс), навіть під час HTTP та читання датчика.
Портал відкривається після завершення поточної операції головного циклу.
Керування виходами потребує зв'язку із сервером: `/api/v1/button/` змінює
спільний із вебпанеллю стан та зберігає перевірки датчика, перегріву,
PID і активної варки. Відхилена дія або помилка зв'язку — 3 біпи.
Автоматично повторювати перемикання після помилки прошивка не буде.
Вимкнення обох працює й без сервера: виходи залишаються заблокованими, поки
сервер не підтвердить зупинку. Запит зупинки повторюється після відновлення
зв'язку; до підтвердження нові кліки не вмикають обладнання.
Оновіть сервер і прошивку перед використанням.

### RGB-індикація HW-479

RGB показує стан контролера та варки:

| Індикація | Стан |
| --- | --- |
| Зелений | Справна плата, звичайний режим |
| Синій | Сесія варки створена, але ще не розпочата |
| Синій блимає | Варка триває, включно з нагріванням |
| Жовтий блимає | Запуск, налаштування Wi-Fi або очікування першого стану сервера |
| Помаранчевий із червоним відтінком | Варка на паузі або очікує дії користувача (`waiting_temperature`) |
| Червоний | Аварія контролера поза варкою |
| Червоний блимає | Помилка під час активної/призупиненої варки або статус `failed` |

Помилки мають пріоритет над іншими станами: несправний датчик температури,
локальний захист виходів, перегрів із сервера, втрата Wi-Fi після реєстрації
або відсутність успішного опитування команд понад 10 секунд. Завершена або
скасована варка повертає звичайний режим, якщо помилок немає. Локальна
аварія виходів залишається червоною до скидання захисту новою командою.
Блимання: 500 мс увімкнено / 500 мс вимкнено; окрема FreeRTOS-задача
підтримує його під час HTTP-запитів і зчитування датчика.

Підключення каналів HW-479: `R` → GPIO16, `G` → GPIO17, `B` → GPIO18.
Для модуля зі спільним катодом підключіть спільний контакт до GND;
за замовчуванням `RGB_ACTIVE_HIGH=1`. Для спільного анода використовуйте
спільний контакт 3,3 V та `RGB_ACTIVE_HIGH=0`. Перевірте тип і маркування
свого модуля; канали повинні мати струмообмежувальні резистори.
Піни задаються через `RGB_RED_PIN`, `RGB_GREEN_PIN`, `RGB_BLUE_PIN`
у `platformio.ini`. Синій канал позначає створену або активну варку.
Колір паузи: червоний канал 100%, зелений приблизно 19% (PWM 48/255).
Після змін зберіть і завантажте прошивку на ESP32.

### Buzzer

Прошивка подає короткий сигнал (150 мс) при запуску ESP32 і зміні ревізії
ручного керування, два сигнали при старті нового варіння та три при зміні
індексу стадії (включно із завершенням останньої). Сигнали виконуються окремою
задачею без блокування керування ТЕНом. Автоматичні перемикання SSR у PID
не спричиняють писк. Зміни ручного керування через захист також можуть подати сигнал.

За замовчуванням використовується пасивний buzzer з тоном 3000 Гц на GPIO27.
У `platformio.ini`: `BUZZER_OUTPUT_PIN` задає пін, `BUZZER_ACTIVE_HIGH=0`
вмикає активний LOW для активного buzzer, `BUZZER_ACTIVE=1` задає активний
buzzer, `BUZZER_ACTIVE=0` — пасивний.
`BUZZER_FREQUENCY_HZ` задає частоту пасивного buzzer, `BUZZER_PULSE_MS` —
тривалість кожного писку. Пауза між писками — 100 мс. Для підбору частоти
змініть `BUZZER_FREQUENCY_HZ` і перепрошийте плату; порівнюйте звучання
при однаковій тривалості. Поточні параметри виводяться в Serial Monitor.
Для модуля з входами VCC/GND/S підключіть S до GPIO27, GND до спільної землі,
VCC до живлення, зазначеного виробником; вхід S має підтримувати 3,3 V.
Для окремого buzzer використовуйте відповідний транзисторний драйвер,
якщо його струм або напруга не відповідають можливостям GPIO.

Звуки ручних дій і варіння надходять після опитування сервера (інтервал 3 с).
Повторний стан не повторює звук. Перше опитування після перезапуску лише
запам'ятовує стан; попередні події не відтворюються. Під час відсутності
зв'язку сигнали не надходять; кілька змін між опитуваннями об'єднуються.
Потрібно оновити сервер і прошити ESP32 (`platformio run --target upload`).

На сторінці контролера кнопка **ТЕН і помпа** відкриває `/controllers/<id>/direct/`:
два незалежні ON/OFF перемикачі та кнопка вимкнення всіх виходів.
ТЕН працює без PID, SSR перемикається через GPIO25. Помпа керується GPIO26.
PID і пряме керування взаємно виключаються. Втрата Wi-Fi, команд або даних
датчика на 10 секунд вимикає виходи. Перегрів також вимикає виходи;
межа береться з налаштувань температурного керування.

Підключення **готового релейного модуля** JQC-3FF-S-Z з входами `− / + / S`:

- `−` → GND ESP32.
- `+` → стабільне 5 V (VIN/5V плати за наявності там живлення 5 V).
- `S` → GPIO26, якщо модуль підтримує логічний сигнал 3,3 V.
- `+24 V` окремого блока живлення → COM.
- NO → `+` помпи; `−` помпи → `−24 V` блока живлення. NC не використовується.

Позначення JQC-3FF-S-Z стосується самого реле, тому сумісність входу S
та активний рівень потрібно перевірити для конкретної плати модуля.
Прошивка за замовчуванням використовує HIGH для ON; для модуля з активним LOW
встановіть `PUMP_RELAY_ACTIVE_HIGH=0` у `platformio.ini`.
Саму котушку реле без модуля не підключайте до GPIO: потрібен драйвер із
захистом від зворотного імпульсу. Помпа живиться від окремого 24 V джерела.

Стан виходів підтверджується телеметрією ESP32. 3,3 V для SSR — розрахунковий
керуючий сигнал. Напруга та струм помпи вимірюються INA226 незалежно від стану
реле. Без датчика, при помилці I²C, переповненні або застарілому звіті показується
`—`, без підстановки номінальних 24 V. ADC SSR відображається окремо.

### INA226: напруга та струм помпи

Підключення логіки: VCC → 3V3 ESP32, GND → спільний GND ESP32 та мінус
24 V джерела, SDA → GPIO21, SCL → GPIO22. Адреса за замовчуванням `0x40`.
Підключення силового кола: `+24 V → COM реле → NO → VIN+ INA226 → VIN− INA226
→ плюс помпи`; мінус помпи → мінус 24 V джерела. Якщо модуль має окремий вхід VBUS, підключіть його до плюса помпи
(після шунта). Таким чином напруга VBUS
відносно GND є напругою на помпі, а струм проходить через шунт датчика.

У `platformio.ini` можна змінити адресу, SDA/SCL і `INA226_SHUNT_OHMS`.
Значення 0,1 Ом відповідає шунту **R100**; перевірте маркування модуля.
Для **R010** встановіть `INA226_SHUNT_OHMS=0.01f`, для **R002** — `0.002f`.
Без перевірки шунта показаний струм може бути неправильним.
Струм в амперах обчислюється зі знакового падіння напруги на шунті та його
опору. Відсутній модуль повторно опитується кожен цикл, не блокуючи ТЕН.

Діагностика INA226 доступна через `pio device monitor --baud 115200` після
прошивання. При запуску виводяться SDA/SCL, адреса, відповіді на адресах
`0x08..0x77` (кандидати INA226: `0x40..0x4F`) та ідентифікатори чипа (manufacturer `0x5449`, device `0x2260` або `0x2261`), а також прочитана конфігурація (очікується `0x4127`). ACK означає лише
наявність I²C пристрою за цією адресою. Якщо модуль відсутній, пошук повторюється
не частіше ніж раз на 30 секунд із повторною ініціалізацією драйвера I²C.
Сканування показує рівні SDA/SCL (у спокої обидва HIGH), кількість ACK, NACK
та помилок; при timeout або іншій помилці шини сканування зупиняється.
Читання регістрів використовує STOP після запису вказівника, щоб окремо
діагностувати помилку запису та читання на ESP32. Кожен цикл показує `bus_raw`, `CVRF`,
напругу, `shunt_raw`, падіння на шунті та струм, або конкретну причину відмови.
`address NACK` означає відсутність відповіді за налаштованою адресою;
`I2C timeout` — проблему обміну; `received .../2 bytes` — неповну відповідь.
Перевірте живлення, спільний GND, SDA/SCL та адресу з журналу.
`CVRF=0` означає, що перетворення ще не готове. Напруга `0.000 V` при успішному
читанні — отримане значення: перевірте реле та VBUS та VIN− відносно GND мультиметром.
Напруга зберігається навіть при недоступному струмі. Струм обчислюється
з сирого шунтового ADC: 2,5 мкВ/крок; напруга VBUS — 1,25 мВ/крок.

За [специфікацією TI](https://www.ti.com/product/INA226) максимальна напруга
вимірювальних входів — **36 V**.
Для 24 V помпи потрібен захист від індуктивних викидів; для однонапрямної
DC помпи — відповідний захисний діод паралельно помпі (катод до плюса,
анод до мінуса). Перевірте робочий і пусковий струм помпи та допустиму
потужність шунта модуля. Діапазон шунтового ADC ±81,92 мВ для R100 відповідає
приблизно ±0,819 A, але це не гарантує допустимий струм конкретної плати.

Після оновлення виконайте `python manage.py migrate` та прошийте ESP32 новою
прошивкою (`platformio run --target upload`).

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
