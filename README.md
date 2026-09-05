# solar-relay

[![CI](https://github.com/peeraponggis/solar-relay/actions/workflows/ci.yml/badge.svg)](https://github.com/peeraponggis/solar-relay/actions/workflows/ci.yml)
[![Docker image](https://github.com/peeraponggis/solar-relay/actions/workflows/docker.yml/badge.svg)](https://github.com/peeraponggis/solar-relay/actions/workflows/docker.yml)
![ghcr](https://img.shields.io/badge/ghcr.io-peeraponggis%2Fsolar--relay-blue)

Relay กลางสำหรับ inverter / hybrid inverter หลายยี่ห้อ อ่านข้อมูลจากอุปกรณ์ (local) หรือ cloud ของผู้ผลิต
แปลงเป็น schema เดียว แล้วส่งต่อไป InfluxDB, MQTT, Home Assistant (auto-discovery) และ PVOutput

```
adapters (sunspec | modbus | solarman | goodwe | fronius_solarapi | sigen_openapi | cloud:*)
   -> Reading (pv_w, ac_w, grid_w, load_w, batt_w, soc, energy_*_kwh, alarms[])
   -> outputs (influxdb | mqtt | homeassistant | pvoutput | console)
```

## ยี่ห้อที่รองรับ

| ยี่ห้อ | Local (แนะนำ) | Cloud (สำรอง) | หมายเหตุการติดตั้ง |
|---|---|---|---|
| Huawei SUN2000 | `modbus` map `huawei` (SDongle TCP 502, unit 1) | `cloud:huawei` Northbound | ขอ Northbound account จากผู้ติดตั้ง; getDevRealKpi จำกัด 1 ครั้ง/5 นาที |
| Sigenergy | `modbus` map `sigen_local` (unit 247, ผู้ติดตั้งต้องเปิด Modbus TCP) | `sigen_openapi` (push ผ่าน MQTT, vendor account) | OpenAPI ต้องบอร์ดเป็น vendor; Sigen push telemetry ทุก 5 นาที + alarm |
| Solis | `modbus` map `solis` (DLS-L / S2-WL-ST port 502, หรือ RS485 ตรง 9600) / `solarman` (DLS-W) | `cloud:soliscloud` v2 | S3-WIFI-ST ไม่มี local เลย; datalogger บางรุ่นปิด port 502 หลัง OTA |
| SolarEdge | `sunspec` (port 1502, unit 1, meter ตามหลัง) | `cloud:solaredge` (300 req/วัน) | เปิด Modbus TCP ใน SetApp |
| Fronius | `sunspec` (unit 1 + 240 meter) หรือ `fronius_solarapi` (JSON) | `cloud:fronius` Solar.web API (เสียเงิน) | ตั้ง SunSpec Model Type = int+SF |
| SMA | `sunspec` (unit 3) | `cloud:sma` (unofficial, production เท่านั้น) | เปิด Modbus TCP ใน web UI ของ inverter |
| Sungrow SH/SG | `modbus` map `sungrow` (WiNet-S 502) | `cloud:sungrow` iSolarCloud OpenAPI | WiNet-S ต้อง white-list IP ของ relay |
| GoodWe | `goodwe` (UDP 8899) หรือ `sunspec` | `cloud:goodwe` SEMS (unofficial) | family ET / ES / DT |
| SolaX | `modbus` map `solax` (Pocket LAN 502) หรือ `sunspec` | ผ่าน SolaXCloud (ยังไม่ทำ) | |
| Delta | `sunspec` | - | RPI / M-series |
| Deye | `solarman` map `deye_1p` / `deye_3p` หรือ `modbus` | `cloud:solarman` (Deye Cloud) | logger serial 10 หลักบน stick |
| Sofar | `solarman` map `sofar` | `cloud:solarman` | |
| Growatt | (Modbus RTU ผ่าน map เพิ่มเองได้) | `cloud:growatt` ShineServer (unofficial) | |

## เริ่มใช้งาน

```bash
pip install -e ".[all,dev]"
cp config.example.yaml config.yaml     # แก้ host / serial / key
cp .env.example .env
python -m solar_relay --config config.yaml --dry-run --once    # อ่านทุกอุปกรณ์ 1 รอบ พิมพ์ JSON
python -m solar_relay --config config.yaml                     # รันต่อเนื่อง
python -m solar_relay --list-adapters
```

Docker (relay + InfluxDB + Mosquitto + Grafana):

```bash
mkdir config && cp config.example.yaml config/config.yaml && cp .env.example .env
docker compose up -d            # ดึง image สำเร็จรูปจาก GHCR (amd64 + arm64 / Raspberry Pi)
docker compose up -d --build    # หรือ build เองจากซอร์ส
```

Image เดี่ยว: `ghcr.io/peeraponggis/solar-relay:latest` (tag `sha-xxxxxxx` ทุก commit บน main และ `1.2.3` เมื่อ push tag `v1.2.3`)
รันเป็น user ไม่ใช่ root อยู่ในกลุ่ม dialout ต่อ RS485 USB ได้ด้วย `--device /dev/ttyUSB0`

```bash
docker run -d --name solar-relay -v $PWD/config:/config:ro --env-file .env ghcr.io/peeraponggis/solar-relay:latest
```

## CI / CD

- `.github/workflows/ci.yml` รัน ruff + pytest บน Python 3.11-3.13 ตรวจว่า dashboard/docs ที่ generate ตรงกับสคริปต์ และ smoke test CLI ทุก push/PR
- `.github/workflows/docker.yml` build image multi-arch ด้วย buildx แล้ว push ไป GHCR เมื่อ push main หรือ tag `v*` (PR แค่ build ไม่ push) พร้อม smoke test `--list-adapters`
- `.github/workflows/release.yml` เมื่อ push tag `v*` จะสร้าง GitHub Release อัตโนมัติ ใส่ release notes จากหัวข้อของเวอร์ชันนั้นใน CHANGELOG.md บวกคำสั่ง docker pull และแนบ wheel/sdist สำหรับ tag ที่มีอยู่แล้วให้รันด้วยมือที่ Actions → Release → Run workflow ใส่ชื่อ tag
- ออก release: เพิ่มหัวข้อ `## vX.Y.Z` ใน CHANGELOG.md, ปรับ version ใน pyproject.toml และ solar_relay/__init__.py แล้ว `git tag vX.Y.Z && git push --tags`

## ทดสอบกับ inverter จริงที่หน้างาน

```bash
python -m solar_relay.probe 192.168.1.30                        # สแกน port, SunSpec และทุก brand map แล้วเสนอ config
python -m solar_relay.probe 192.168.1.50 --serial 2712345678    # Solarman stick
python -m solar_relay.probe --rtu COM3 --baud 9600 --maps solis # RS485 ตรง
```

ขั้นตอนเต็ม เช็กลิสต์ต่อยี่ห้อ (ต้องเปิดอะไร port/unit อะไร) และวิธีตรวจเครื่องหมาย grid/battery อยู่ที่ [docs/SITE_TEST.md](docs/SITE_TEST.md)

## Grafana dashboard

`docker compose up` จะ provision datasource InfluxDB และ dashboard **Solar Relay - Overview** (โฟลเดอร์ Solar) ให้อัตโนมัติ
เปิดที่ http://localhost:3000 (admin / ค่า `GRAFANA_PASS` ใน .env)

- ตัวกรอง Device และ Brand ด้านบน เลือกได้หลายค่า
- แถว KPI: PV, Load, Grid (+ซื้อ/-ขาย), Battery (+ชาร์จ/-คาย), SOC, Energy วันนี้, Active alarms, Devices offline
- ตาราง Device status ค่าล่าสุดต่ออุปกรณ์ (offline และ alarm ขึ้นสีแดง)
- กราฟ Power flow, Battery SOC, Energy per day, PV strings, Temperatures, Grid voltage/frequency
- Alarm log จาก measurement `alarm` และ annotation สีแดงบนทุกกราฟเมื่อมี alarm เกิด

ไฟล์ JSON สร้างจาก `grafana/build_dashboard.py` หากแก้ query ให้แก้ที่สคริปต์แล้วรัน `python grafana/build_dashboard.py` (มี test ตรวจว่า JSON ตรงกับสคริปต์)

## Home Assistant dashboard

output `homeassistant` ประกาศ entity ผ่าน MQTT discovery ด้วยชื่อคงที่ `sensor.<device>_pv_w`, `sensor.<device>_soc`,
`binary_sensor.<device>_alarm`, `sensor.<device>_alarms` (attribute `alarms` มี code/message/advice) และ `sensor.<device>_status`
(`<device>` คือ id ใน config แปลงเป็น slug เช่น `huawei-sun2000` → `huawei_sun2000`)

สร้าง Lovelace dashboard จาก config ได้ทันที (ใช้ card มาตรฐานของ HA ไม่ต้องติดตั้ง HACS):

```bash
python homeassistant/build_dashboard.py --config config.yaml
```

ได้ไฟล์ `homeassistant/solar-relay-dashboard.yaml` (ตัวอย่างจาก config.example.yaml commit ไว้แล้ว) นำเข้าโดย
Settings → Dashboards → Add dashboard → เปิด → ดินสอ → ⋮ → Raw configuration editor → วาง YAML
หรือใส่ `lovelace: dashboards:` แบบ `mode: yaml` ใน configuration.yaml ตามคอมเมนต์หัวสคริปต์

- **Overview** การ์ดต่ออุปกรณ์ (สถานะ, PV/Load/Grid/Battery, gauge SOC, พลังงานวันนี้) และกล่อง alarm พร้อมคำแนะนำแก้ไขที่โผล่เฉพาะเมื่อมี alarm
- **Alarms** รวม alarm ทุกเครื่อง + คำแนะนำจาก alarm_catalog
- **หน้าต่ออุปกรณ์** history-graph power flow 24 ชม., SOC, กราฟแท่งพลังงานรายวัน 14 วัน, รายละเอียด string/แรงดัน/อุณหภูมิ
- Energy dashboard ของ HA: เพิ่ม `sensor.<device>_energy_total_kwh` เป็น Solar production, `grid_import/export_day_kwh` เป็น Grid, `batt_charge/discharge_day_kwh` เป็น Battery

## ตาราง alarm รวมทุกยี่ห้อ + คำแนะนำแก้ไข

`solar_relay/alarm_catalog.yaml` รวมรหัส error ของ Huawei (alarm ID), Solis (รหัสหน้าจอ เช่น OV-G-V, ISO-PRO), Sungrow (002-323),
Deye (F01-F64), Sofar (ID01-ID84), SolaX (IE01-IE32), GoodWe (ชื่อ error), SunSpec Evt1 (SolarEdge/Fronius/SMA/Delta), SolarEdge (18xNN),
Fronius (state code), SMA (event number), Growatt และ Sigen โดยแต่ละรหัสผูกกับ **category** (เช่น insulation, leakage, arc, grid_overvoltage)
ที่มีสาเหตุและขั้นตอนแก้ไขภาษาไทยสำหรับทีมบริการ

- relay เติม `message`, `advice`, `category` และปรับ `severity` ให้ทุก alarm อัตโนมัติก่อนส่งออก (InfluxDB measurement `alarm` มี tag `category` และ field `advice`)
- ดูตารางทั้งหมดที่ [docs/ALARM_CODES.md](docs/ALARM_CODES.md) (สร้างด้วย `python -m solar_relay.alarm_catalog --markdown > docs/ALARM_CODES.md`)
- ค้นรหัสจาก CLI: `python -m solar_relay.alarm_catalog --lookup huawei.2062 deye.F16 --message "OV-G-V02"`
- เพิ่มรหัสใหม่: ใส่ใต้ `brands.<ยี่ห้อ>` ระบุ `name`, `category` (หรือ `action` เอง) และ `aliases` สำหรับข้อความที่ cloud ส่งมา
- รายการ Sigen ยังเป็น placeholder เพราะหน้า Error Code List ของ portal ต้องใช้บัญชี vendor เปิด ให้เติมเมื่อได้รหัสจริง

## Schema กลาง (`solar_relay/schema.py`)

เครื่องหมายทุกยี่ห้อถูกแปลงให้เหมือนกัน:

| field | ความหมาย |
|---|---|
| `pv_w` | กำลัง DC จากแผง (>= 0) |
| `ac_w` | กำลัง AC ที่ inverter จ่าย |
| `grid_w` | + ซื้อไฟจาก grid, - ขายไฟเข้า grid |
| `batt_w` | + ชาร์จ, - คายประจุ |
| `load_w` | โหลดบ้าน/โรงงาน (คำนวณจาก balance ถ้ายี่ห้อไม่ให้) |
| `soc`, `soh`, `batt_v`, `batt_a`, `batt_temp_c` | แบตเตอรี่ |
| `energy_day_kwh`, `energy_total_kwh`, `grid_import_day_kwh`, `grid_export_day_kwh`, `batt_charge_day_kwh`, `batt_discharge_day_kwh`, `load_day_kwh` | พลังงาน |
| `status`, `online`, `alarms[]` (code, message, severity, active) | สถานะ / alarm สำหรับทีมบริการ |
| `strings{pv1..}` | แรงดัน กระแส กำลัง ราย string |

## เพิ่มยี่ห้อใหม่

1. ถ้าเป็น SunSpec ใช้ `adapter: sunspec` ได้เลย
2. ถ้ามี register map ของตัวเอง เพิ่ม list ของ `Reg(...)` และฟังก์ชัน `finalize_*` ใน `solar_relay/adapters/modbus_maps.py` แล้วลงทะเบียนใน `MAPS`
3. ถ้าเป็น cloud สืบทอด `CloudAdapter` ใน `solar_relay/adapters/cloud/` แล้วเพิ่ม key ใน `solar_relay/registry.py`

## ทดสอบ

```bash
pytest -q
```

## ข้อควรระวัง

- Register map ของ Solis, Sungrow, SolaX, Deye, Sofar, Sigen local ถอดจากเอกสารและโปรเจกต์ชุมชน ควรตรวจกับ PDF ของ firmware ที่ใช้จริงก่อนนำค่าไปควบคุมอะไร
- Cloud ที่เป็น unofficial (GoodWe SEMS, Growatt ShineServer, SMA Sunny Portal) อาจเปลี่ยนได้ทุกเมื่อ
- Modbus บน RS485 มี master ได้ตัวเดียว ถ้า datalogger ของผู้ผลิตยังต่ออยู่ให้ใช้ Waveshare RS485-to-ETH โหมด multi-host (ดู alienatedsec/solis-ha-modbus-cloud)
