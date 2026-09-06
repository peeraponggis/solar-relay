# ทดสอบกับ inverter จริงที่หน้างาน

เป้าหมาย: ภายใน 30 นาทีต่ออุปกรณ์ รู้ว่า (1) ต่อถึงหรือไม่ (2) ใช้ adapter/map ไหน (3) ค่าที่อ่านถูกต้องและเครื่องหมายถูกทิศ

## เตรียมก่อนไปหน้างาน

- โน้ตบุ๊กที่ติดตั้ง `pip install -e ".[all,dev]"` แล้ว รัน `python -m solar_relay --list-adapters` ได้
- สาย LAN + สวิตช์เล็ก 1 ตัว (ต่อขนานกับ datalogger), USB-RS485 adapter (สำหรับ Solis/Deye/Growatt ต่อตรง)
- แอปผู้ติดตั้งของแต่ละยี่ห้อ (SUN2000 app, SolisCloud, iSolarCloud, SolaXCloud, SEMS, mySigen) เพื่อเปิด Modbus TCP และดูค่าเทียบ
- ขอ IP ของ inverter/datalogger จาก router หรือแอป และตั้ง **static IP / DHCP reservation**

## ขั้นตอนต่ออุปกรณ์

1. **สแกน** ให้เครื่องมือหาวิธีต่อและ map ที่ถูกให้ ถ้ายังไม่รู้ IP ให้กวาดทั้งวงก่อน (เครื่องต้องอยู่ Wi-Fi/LAN วงเดียวกับ inverter)
   ```bash
   python -m solar_relay.probe --scan                    # กวาดวง /24 ของเครื่องนี้ หา port 502/1502/6607/8899 แล้วตรวจทุกตัวที่เจอ
   python -m solar_relay.probe --scan 192.168.10.0/24    # ระบุวงเอง
   python -m solar_relay.probe 192.168.1.30
   python -m solar_relay.probe 192.168.1.50 --serial 2712345678     # Solarman stick (Deye / Sofar / Solis DLS-W)
   python -m solar_relay.probe --rtu COM3 --baud 9600 --maps solis  # RS485 ตรง
   ```
   ผลลัพธ์บรรทัดที่มี `*` และ score สูงสุดคือคำตอบ ท้ายผลมี `devices:` ให้คัดลอกลง config.yaml
   ถ้า `--scan` เจอเครื่องใน ARP แต่ไม่มี port เปิด แปลว่าอุปกรณ์อยู่ในวงแต่ **ยังไม่เปิด Modbus TCP** (Huawei SDongle ปิดเป็นค่าเริ่มต้น) ต้องเข้าแอปผู้ผลิตเปิด 1 ครั้ง
2. **อ่าน 1 รอบ** แล้วเทียบกับหน้าจอ/แอปของผู้ผลิต ณ เวลาเดียวกัน
   ```bash
   python -m solar_relay --config config.yaml --dry-run --once
   ```
   เทียบ pv_w, ac_w, soc, energy_day_kwh ควรต่างกันไม่เกิน 2-3% (เวลาอ่านต่างกันไม่กี่วินาที)
3. **ตรวจเครื่องหมาย** ของ grid_w และ batt_w (สำคัญที่สุด ยี่ห้อต่างกันกลับทิศกันบ่อย)
   - เปิดโหลดใหญ่ (กาต้มน้ำ/แอร์) ให้บ้านซื้อไฟ → `grid_w` ต้อง **บวก** ปิดโหลดกลางแดดให้ขายไฟ → **ลบ**
   - ช่วงแบตชาร์จ `batt_w` ต้อง **บวก** ช่วงคาย **ลบ** (ดูจากแอปว่ากำลังชาร์จหรือคาย)
   - ถ้ากลับทิศ: SunSpec ใส่ `meter_inverted: true` ใน options ยี่ห้ออื่นแจ้งรุ่น + ค่าที่อ่านได้ เพื่อแก้ `finalize_*` ใน modbus_maps.py
4. **ปล่อยรัน 10 นาที** ดูว่าไม่มี "read failed" ซ้ำ
   ```bash
   python -m solar_relay --config config.yaml --dry-run
   ```
   ถ้าอ่านได้บ้างไม่ได้บ้าง ลด `max_block` เหลือ 40 หรือเพิ่ม `interval_s` (WiFi dongle ส่วนใหญ่รับได้ ~1 request/วินาที)
5. **ทดสอบ alarm** ถ้าทำได้ ปิดเบรกเกอร์ AC 1 นาที ควรเห็น alarm grid loss (huawei.2032, solis.NO-GRID, deye.F35 ...) พร้อม advice แล้วหายเมื่อเปิดกลับ

## เช็กลิสต์ต่อยี่ห้อ

| ยี่ห้อ | ต้องเปิดอะไร | port / unit | ข้อควรระวัง |
|---|---|---|---|
| Huawei SUN2000 + SDongle | แอป SUN2000 → Settings → Communication → Dongle parameter → Modbus TCP = Enable (unrestricted) | 502 unit 1 (fw เก่า 6607) | SDongle รับ client ได้ 1-2 ตัว ถ้า FusionSolar ใช้ Modbus อยู่จะชนกัน; LUNA2000/meter อ่านผ่าน unit เดียวกัน |
| Sigenergy | ผู้ติดตั้งเปิด Modbus TCP ในแอป mySigen (โหมด installer) | 502 plant unit 247, inverter unit 1.. | ต้อง static IP; ถ้าอ่านไม่ได้เลยให้ถามผู้ติดตั้งว่าเปิด "third-party Modbus" แล้วหรือยัง |
| Solis + DLS-L / S2-WL-ST / S3-WIFI-ST | เปิด Modbus TCP ใน web UI ของ logger (10.10.100.254) หรือแอป | 502 unit 1 | บาง firmware ปิด port 502 หลัง OTA; S2-WL-ST หลุด cloud เมื่อมี TCP 2 connection; DLS-W ใช้ Solarman 8899 แทน |
| Solis RS485 ตรง | ต่อ A/B ที่ COM port (Exceedconn EC04681-2014-BF) | 9600 8N1 unit 1 | ห้ามมี master 2 ตัวบนบัส ถ้า logger ยังต่ออยู่ให้ใช้ Waveshare RS485-to-ETH โหมด multi-host |
| SolarEdge | SetApp → Site Communication → Modbus TCP = Enable | 1502 unit 1 (meter unit ถัดไป) | ไฟล์ SunSpec ถูกปิดอัตโนมัติถ้าไม่มี client ใน 2 นาทีบางรุ่น; เปิดใหม่ใน SetApp |
| Fronius | Web UI → Modbus → SunSpec Modbus TCP = on, Model type = **int + SF** | 502 unit 1, meter 240 | ถ้าเลือก float จะอ่านผิด; Gen24 ต้องตั้ง Inverter control via Modbus ตามต้องการ |
| SMA | Web UI (installer) → Device parameters → External communication → Modbus TCP = Yes | 502 unit 3 (Sunny Island 126) | ใช้ unit 3 ไม่ใช่ 1; login installer เท่านั้นที่เห็นเมนู |
| Sungrow WiNet-S | Web UI WiNet-S (installer) → Communication → Modbus TCP: enable, white-list IP ของ relay | 502 unit 1 | ไม่ white-list จะต่อไม่ได้แม้ port เปิด; SH ไม่ใช่ SunSpec ใช้ map sungrow |
| GoodWe | ไม่ต้องตั้ง (UDP 8899) | 8899 | ใช้ `adapter: goodwe` ไม่ใช่ solarman; ระบุ family ET/ES/DT ถ้า auto ไม่เจอ |
| SolaX Pocket LAN/WiFi 3.0 | SolaXCloud/แอป → Modbus TCP function = on | 502 unit 1 | Pocket WiFi 1.0/2.0 ไม่มี Modbus TCP |
| Deye / Sofar (Solarman stick) | ไม่ต้องตั้ง แต่ต้องรู้ serial 10 หลักบน stick | 8899 unit 1 | ถ้า stick ต่อ cloud อยู่บางครั้งช้า ใช้ `--timeout 10`; Deye 3 เฟสใช้ map deye_3p |
| Delta | RPI web/LCD → Modbus TCP enable | 502 unit 1 | SunSpec |

## บันทึกผลกลับมา

ต่ออุปกรณ์ 1 เครื่อง ส่ง 3 อย่างนี้กลับมา ผมจะปรับ map/sign และเพิ่มรหัส alarm ให้ตรงหน้างานได้

1. ผล `python -m solar_relay.probe <ip> --json > probe-<site>-<device>.json`
2. ผล `python -m solar_relay --config config.yaml --dry-run --once > reading-<site>-<device>.jsonl` พร้อมภาพหน้าจอแอปผู้ผลิตเวลาเดียวกัน
3. รุ่น inverter, รุ่น datalogger และเวอร์ชัน firmware (จากแอปหรือหน้าจอ)

ไม่ต้องส่ง config.yaml ที่มี key/รหัสผ่าน cloud
