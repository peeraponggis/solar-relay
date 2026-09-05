# solar-relay

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
docker compose up -d --build
```

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
