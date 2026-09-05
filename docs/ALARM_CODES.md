# Alarm / error code reference (all brands)

Generated from `solar_relay/alarm_catalog.yaml` by `python -m solar_relay.alarm_catalog --markdown`.

## Categories (shared guidance)

| category | name | typical cause | action |
|---|---|---|---|
| `grid_loss` | Grid loss / no AC | ไฟกริดดับ, เบรกเกอร์ AC ตัด, สายเฟส/นิวทรัลหลวม, ฟิวส์ AC ขาด | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `grid_overvoltage` | Grid overvoltage | แรงดันกริดสูงเกิน setting ประเทศ (มักเกิดช่วงเที่ยงที่ระบบใกล้เคียง export มาก) หรือสาย AC ยาว/เล็กทำให้แรงดันปลายสายยกขึ้น | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `grid_undervoltage` | Grid undervoltage | แรงดันกริดต่ำ, สาย AC หลวม, โหลดหนักในซอย, เฟสหาย | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `grid_frequency` | Grid frequency out of range | ความถี่กริดเกิน/ต่ำกว่าช่วงที่ตั้ง (ไทย 50 Hz ±1) หรือเป็นระบบ off-grid/เจนเนอเรเตอร์ที่ความถี่แกว่ง | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `grid_impedance` | Grid impedance too high | สาย AC ยาว/เล็ก จุดต่อหลวม หม้อแปลงขนาดเล็ก | ตรวจจุดต่อ AC ทุกจุด เพิ่มขนาดสายหรือลดระยะ ปรับค่า impedance protection ได้เฉพาะเมื่อการไฟฟ้าอนุญาต |
| `islanding` | Islanding detected | inverter ตรวจพบว่ากริดหาย (anti-islanding) มักเกิดพร้อมกริดดับหรือกริดอ่อนมาก | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `dc_overvoltage` | PV / DC overvoltage | จำนวนแผงต่ออนุกรมมากเกินไป (Voc รวมสูงกว่า Vmax ของ inverter) โดยเฉพาะตอนเช้าอากาศเย็น | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `dc_reverse` | PV string reverse polarity | ต่อขั้ว +/- ของ string สลับ | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `string_abnormal` | String current / power abnormal | string ใดผลิตต่ำผิดปกติ (เงาบัง แผงเสีย ฟิวส์ขาด คอนเนกเตอร์ MC4 ร้อน/หลวม) | เทียบกระแสแต่ละ string ในแอป/dashboard (PV strings panel) string ที่ต่ำกว่าเพื่อนเกิน 20% ให้ตรวจเงาบัง คอนเนกเตอร์ MC4 ฟิวส์ และแผงด้วยกล้องความร้อน |
| `string_backfeed` | String current backfeed | string มี Voc ไม่เท่ากัน (จำนวนแผงต่างกัน หรือมีแผงเสีย) ทำให้กระแสไหลย้อน | ตรวจว่าทุก string ที่ขนานกันมีจำนวนแผงและรุ่นเท่ากัน วัด Voc แต่ละ string |
| `insulation` | Low insulation resistance (ISO / PV ground fault) | ฉนวนสาย DC รั่วลงดิน (สายถลอก, น้ำเข้ากล่องต่อสาย/MC4, ความชื้นตอนเช้า, แผงแตก) | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `leakage` | Residual / leakage current too high (RCMU, GFCI) | กระแสรั่วลงดินฝั่ง DC หรือ AC เกิน 30-300 mA, capacitance ต่อดินของแผงสูง (แผงเปียก), RCD ที่ติดตั้งไม่ใช่ type A/B | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `arc` | DC arc fault (AFCI) | จุดต่อ DC หลวม/ไหม้ (MC4, ขั้วต่อใน inverter, ฟิวส์) ทำให้เกิดประกายไฟ เสี่ยงไฟไหม้ | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `overtemp` | Over temperature | ระบายความร้อนไม่พอ (ติดตั้งโดนแดด, ระยะห่างไม่พอ, ฝุ่นอุดครีบ, พัดลมเสีย) หรืออุณหภูมิแวดล้อมสูง | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `fan` | Fan failure | พัดลมภายใน/ภายนอกเสียหรือติดฝุ่น | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `relay` | Relay / output relay check failure | รีเลย์ต่อกริดภายในเสีย หรือมีไฟย้อนที่ขั้ว AC ตอนตรวจ | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `dc_injection` | DC component in AC output too high | วงจรภายในผิดปกติ หรือมี DC offset จากโหลด/กริด | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `bus` | DC bus voltage abnormal | บัสภายในแรงดันสูง/ต่ำผิดปกติ มักตามหลัง DC overvoltage หรือแผงแรงดันแกว่ง | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `overcurrent` | Output / input overcurrent | กระแส AC หรือ DC เกินพิกัด (โหลด backup เกิน, string ขนานมากไป, กริดผิดปกติชั่วขณะ) | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `overload` | Backup / EPS overload | โหลดในวงจร backup เกินพิกัดของ inverter ตอนไฟดับ หรือโหลดมอเตอร์กระชากตอนสตาร์ท | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `battery` | Battery abnormal | BMS รายงานผิดปกติ (แรงดันเซลล์สูง/ต่ำ, อุณหภูมิ, กระแสเกิน) หรือแบตเตอรี่ต่อสลับขั้ว | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `battery_comm` | Battery / BMS communication lost | สาย CAN/RS485 ระหว่าง inverter กับแบตเตอรี่หลุด สลับ pin ตั้ง protocol ผิดรุ่น หรือ terminator ไม่ครบ | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `battery_reverse` | Battery reverse connection | ต่อขั้วแบตเตอรี่สลับ | ปิดทุกอย่าง ตรวจขั้ว +/- ก่อนต่อใหม่ ตรวจว่าฟิวส์/เบรกเกอร์แบตยังดี |
| `meter_comm` | Meter / CT communication abnormal | สาย RS485 ไปมิเตอร์หลุด, address/baud ผิด, CT ต่อสลับทิศหรือหลุด | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `comm` | Communication / monitoring unit fault | datalogger/dongle หลุดจากอินเทอร์เน็ต หรือสายภายในหลวม | ตรวจ Wi-Fi/LAN ของ dongle ถอดเสียบใหม่ ตรวจว่า inverter ยังผลิตปกติ (alarm นี้ไม่กระทบการผลิต) |
| `device_fault` | Internal device / hardware fault | ความเสียหายภายใน (sensor, DSP, power stage) | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `firmware` | Firmware / upgrade / license problem | อัปเดตไม่สำเร็จ เวอร์ชันไม่ตรงกัน หรือ license หมดอายุ | อัปเดต firmware ใหม่ผ่านแอปผู้ติดตั้ง หรือติดต่อผู้ผลิตเรื่อง license |
| `config` | Configuration abnormal | ตั้งค่าไม่ตรงกับการติดตั้งจริง (grid code, PV string config, CT, meter, battery type) | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `pv_low` | PV voltage low / no PV | แสงน้อย เช้า-เย็น หรือ string หลุด/DC switch ปิด | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `optimizer` | Optimizer / module-level device fault | optimizer หรืออุปกรณ์ระดับแผงหลุดสื่อสาร/เสีย | ดูแผงที่หายจากแผนผังในแอป ตรวจคอนเนกเตอร์และตัว optimizer ตัวนั้น |

## huawei

| code | name | severity | category | action |
|---|---|---|---|---|
| `2001` | High string input voltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `2002` | DC arc fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `2003` | DC arc fault (manual clear required) | fault | arc | เหมือน 2002 และต้อง clear alarm ด้วยแอป/ปุ่มบนเครื่องหลังตรวจสายเสร็จ |
| `2011` | String reverse connection | fault | dc_reverse | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `2012` | String current backfeed | warning | string_backfeed | ตรวจว่าทุก string ที่ขนานกันมีจำนวนแผงและรุ่นเท่ากัน วัด Voc แต่ละ string |
| `2013` | Abnormal string power | warning | string_abnormal | เทียบกระแสแต่ละ string ในแอป/dashboard (PV strings panel) string ที่ต่ำกว่าเพื่อนเกิน 20% ให้ตรวจเงาบัง คอนเนกเตอร์ MC4 ฟิวส์ และแผงด้วยกล้องความร้อน |
| `2014` | High input string voltage to ground | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `2015` | PV string loss | info | pv_low | string นั้นไม่มีกระแสกลางวัน ตรวจ MC4 ฟิวส์ และแผง |
| `2021` | AFCI self-check fail | fault | arc | รัน AFCI self-check ใหม่จากแอป ถ้าล้มเหลวซ้ำเป็นบอร์ด AFCI เสีย เคลม |
| `2031` | Phase wire short-circuited to PE | fault | grid_loss | สายเฟสช็อตลงดินหรือต่อ N/PE ผิด ตรวจ AC wiring ทั้งหมดก่อนเปิดใหม่ |
| `2032` | Grid loss | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `2033` | Grid undervoltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `2034` | Grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `2035` | Grid voltage imbalance | warning | grid_undervoltage | วัดแรงดัน 3 เฟส ต่างกันเกิน 3-5% แสดงว่าโหลดไม่สมดุลหรือสายเฟสหลวม |
| `2036` | Grid overfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `2037` | Grid underfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `2038` | Unstable grid frequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `2039` | Output overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `2040` | Output DC component overhigh | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `2051` | Abnormal residual current | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `2061` | Abnormal grounding | fault | insulation | ตรวจว่าสาย PE ต่อครบและมีความต่อเนื่อง สาย N/PE ไม่สลับ |
| `2062` | Low insulation resistance | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `2063` | Overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `2064` | Device fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `2065` | Upgrade failed or version mismatch | info | firmware | อัปเดต firmware ใหม่ผ่านแอปผู้ติดตั้ง หรือติดต่อผู้ผลิตเรื่อง license |
| `2066` | License expired | info | firmware | อัปเดต firmware ใหม่ผ่านแอปผู้ติดตั้ง หรือติดต่อผู้ผลิตเรื่อง license |
| `2067` | Faulty power collector | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `2068` | Battery abnormal | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `2069` | Battery reverse connection | fault | battery_reverse | ปิดทุกอย่าง ตรวจขั้ว +/- ก่อนต่อใหม่ ตรวจว่าฟิวส์/เบรกเกอร์แบตยังดี |
| `2070` | Active islanding | warning | islanding | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `2071` | Passive islanding | warning | islanding | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `2072` | Transient AC overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `2075` | Peripheral port short circuit | fault | device_fault | ตรวจสายที่ต่อพอร์ต COM/12V/dry contact ว่าช็อตหรือไม่ |
| `2077` | Abnormal grounding or AC wiring | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `2080` | Abnormal PV module configuration | warning | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `2081` | Optimizer fault | warning | optimizer | ดูแผงที่หายจากแผนผังในแอป ตรวจคอนเนกเตอร์และตัว optimizer ตัวนั้น |
| `2082` | On-grid/off-grid controller abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `2085` | Built-in PID operation abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `2086` | External fan abnormal | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `2087` | Internal fan abnormal | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `2088` | DC protection unit abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `2089` | EL unit abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `2090` | Active adjustment instruction abnormal | warning | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `2091` | Reactive adjustment instruction abnormal | warning | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `2092` | CT wiring abnormal | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `61440` | Faulty monitoring unit | info | comm | ตรวจ Wi-Fi/LAN ของ dongle ถอดเสียบใหม่ ตรวจว่า inverter ยังผลิตปกติ (alarm นี้ไม่กระทบการผลิต) |
| `_default` | Huawei alarm | warning |  | ดูรายละเอียดใน FusionSolar > Alarms ซึ่งมี alarmCause และ repairSuggestion ของ Huawei |

## solis

| code | name | severity | category | action |
|---|---|---|---|---|
| `NO-GRID` (No Grid, NoGrid) | No grid | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `OV-G-V` (OV-G-V01, OV-G-V02, OV-G-V03, OV-G-V04, OV-G-V05) | Grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `UN-G-V` (UN-G-V01, UN-G-V02, UN-G-V03) | Grid undervoltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `OV-G-F` (OV-G-F01, OV-G-F02) | Grid overfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `UN-G-F` (UN-G-F01, UN-G-F02) | Grid underfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `G-IMP` | Grid impedance too high | warning | grid_impedance | ตรวจจุดต่อ AC ทุกจุด เพิ่มขนาดสายหรือลดระยะ ปรับค่า impedance protection ได้เฉพาะเมื่อการไฟฟ้าอนุญาต |
| `G-PHASE` (G-PHASE01, PHASE-ERR) | Grid phase error / unbalance | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `GRID-INTF` (GRID-INTF01, GRID-INTF02) | Grid interference | warning | grid_frequency | กริดมีสัญญาณรบกวน/ฮาร์มอนิกสูง ตรวจโหลดใกล้เคียง (เครื่องเชื่อม |
| `OV-G-I` | Grid overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `OV-DC` (OV-DC01, OV-DC02, OV-DC03, OV-DC04) | DC overvoltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `OV-BUS` | DC bus overvoltage | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `UN-BUS` (UN-BUS01, UN-BUS02) | DC bus undervoltage | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `OV-TEM` | Over temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `PV ISO-PRO` (ISO-PRO, ISO-PRO01, ISO-PRO02, PV ISO-PRO01, PV ISO-PRO02) | PV insulation protection | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `ILeak-PRO` (ILeak-PRO01, ILeak-PRO02, ILeak-PRO03, ILeak-PRO04, ILEAK-PRO) | Leakage current protection | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `RelayCheck-FAIL` (Relay-FAIL, RELAY-FAIL) | Relay check failed | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `DCinj-FAULT` (DCINJ-FAULT) | DC injection fault | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `AFCI-Check` (AFCI-CHECK, AFCI-Check FAIL) | AFCI self-check failed | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `ARC-FAULT` (ARC FAULT) | DC arc fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `IGBT-OV-I` | IGBT overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `DC-INTF` | DC current sampling error | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `12Power-FAULT` | 12 V auxiliary power fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `INI-FAULT` | Initialisation / DSP fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `OV-Vbatt` (OV-VBATT) | Battery overvoltage | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `UN-Vbatt` (UN-VBATT) | Battery undervoltage | fault | battery | SOC ต่ำมาก ปล่อยให้ชาร์จจากกริดหรือ PV ตรวจ setting over-discharge SOC |
| `CAN-FAIL` (BatName-FAIL, CAN Fail) | Battery CAN communication failed | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `Battery-Reverse` (BAT-REVERSE) | Battery reverse polarity | fault | battery_reverse | ปิดทุกอย่าง ตรวจขั้ว +/- ก่อนต่อใหม่ ตรวจว่าฟิวส์/เบรกเกอร์แบตยังดี |
| `OV-ILLC` | LLC overcurrent (battery side) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `OV-VBackup` (OV-VBACKUP) | Backup output overvoltage | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `Over-Load` (OVER-LOAD, Backup Overload) | Backup overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `Meter-FAIL` (METER-FAIL, Meter Fail) | Meter communication failed | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `Failsafe` (FAILSAFE) | Fail-safe (meter lost) export stop | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `SCREEN-COMM-FAIL` | Display communication fail | info | comm | ตรวจ Wi-Fi/LAN ของ dongle ถอดเสียบใหม่ ตรวจว่า inverter ยังผลิตปกติ (alarm นี้ไม่กระทบการผลิต) |
| `DSP-B-FAULT` | DSP B fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `OV-G-V-DC` | Grid voltage DC offset | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `_default` | Solis alarm | warning |  | อ่านรหัสจากหน้าจอ inverter หรือ SolisCloud > Alarm ซึ่งมี advice ประกอบ |

## sungrow

| code | name | severity | category | action |
|---|---|---|---|---|
| `002` (2) | Grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `003` (3) | Transient grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `004` (4) | Grid undervoltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `005` (5) | Grid low voltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `007` (7) | AC instantaneous overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `008` (8) | Grid overfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `009` (9) | Grid underfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `010` (10) | Grid power outage / islanding | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `011` (11) | Device abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `012` (12) | Excessive leakage current | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `013` (13) | Grid abnormal | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `014` (14) | 10-minute grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `015` (15) | Grid overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `016` (16) | Output overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `017` (17) | Grid voltage unbalance | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `019` (19) | Bus overvoltage | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `021` (21) | PV1 overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `022` (22) | PV2 overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `028` (28) | PV1 reverse connection | fault | dc_reverse | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `029` (29) | PV2 reverse connection | fault | dc_reverse | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `036` (36) | Module overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `037` (37) | Ambient overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `038` (38) | Relay fault | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `039` (39) | Low insulation resistance | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `040` (40) | Fan fault | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `041` (41) | Leakage current sensor abnormal | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `043` (43) | Low ambient temperature | info | overtemp | อุณหภูมิต่ำกว่าช่วงทำงาน รอให้อุ่นขึ้น |
| `044` (44) | System fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `047` (47) | PV input configuration abnormal | warning | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `048` (48) | PV current sampling error | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `070` (70) | Fan fault | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `106` | Grounding fault | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `116` | Bus voltage abnormal | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `220` | PV reverse / DC arc | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `300` | Battery undervoltage | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `301` | Battery overvoltage | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `305` | Battery communication abnormal | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `310` | Backup overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `314` | Battery overtemperature | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `323` | Meter communication abnormal | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `state.5500` | Inverter in fault state | fault | device_fault | ดู fault code ใน iSolarCloud หรือหน้าจอ WiNet เพื่อรหัสจริง |
| `state.2500` | Communication fault | info | comm | ตรวจ Wi-Fi/LAN ของ dongle ถอดเสียบใหม่ ตรวจว่า inverter ยังผลิตปกติ (alarm นี้ไม่กระทบการผลิต) |
| `dev_status.2` | Device fault (cloud) | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `_default` | Sungrow fault | warning |  | อ่านรหัส 3 หลักจาก iSolarCloud > Fault แล้วเทียบตารางในคู่มือ |

## deye

| code | name | severity | category | action |
|---|---|---|---|---|
| `F01` | DC input polarity reverse | fault | dc_reverse | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `F07` | DC/DC overcurrent (soft) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F08` | DC/DC overcurrent (hard) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F10` | Auxiliary power supply fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `F13` | Working mode changed / grid mode changed | info | config | เกิดเมื่อสลับ on-grid/off-grid หรือเปลี่ยน grid standard เป็นข้อมูล ไม่ต้องแก้ |
| `F15` | AC overcurrent (software) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F16` | AC leakage current (GFCI) | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `F18` | AC overcurrent (hardware) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F20` | DC overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F22` | Emergency stop / remote shutdown | info | config | ตรวจสวิตช์ E-stop หรือคำสั่ง shutdown จาก remote |
| `F23` | AC leakage current transient | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `F24` | DC insulation impedance failure | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `F26` | DC busbar unbalanced | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F29` | Parallel communication fault | info | comm | ตรวจสาย parallel CAN ระหว่างเครื่อง terminator และ master/slave setting |
| `F33` | AC overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F34` | AC overload (backup) | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `F35` | No AC grid | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `F41` | Parallel system stopped | info | comm | ตรวจ Wi-Fi/LAN ของ dongle ถอดเสียบใหม่ ตรวจว่า inverter ยังผลิตปกติ (alarm นี้ไม่กระทบการผลิต) |
| `F42` | AC line low voltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `F47` | AC overfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `F48` | AC underfrequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `F55` | DC busbar voltage too high | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `F56` | DC busbar voltage too low / battery voltage low | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `F58` | BMS communication fault | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `F62` | DRM / remote shutdown | info | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `F63` | ARC fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `F64` | Heat sink high temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `_default` | Deye fault | warning |  | ดู F-code บนหน้าจอหรือ Solarman แล้วเทียบตาราง Fault ในคู่มือ Deye |

## sofar

| code | name | severity | category | action |
|---|---|---|---|---|
| `ID01` | Grid overvoltage (GridOVP) | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `ID02` | Grid undervoltage (GridUVP) | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `ID03` | Grid overfrequency (GridOFP) | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `ID04` | Grid underfrequency (GridUFP) | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `ID05` | PV undervoltage | info | pv_low | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `ID09` | Grid overvoltage instantaneous | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `ID10` | Grid 10-min overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `ID12` | Grid undervoltage instantaneous | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `ID14` | Grid frequency abnormal | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `ID17` | Grid current sampling error | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `ID18` | DC injection current | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `ID21` | Leakage current sampling error | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `ID24` | Insulation resistance low | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `ID25` | Leakage current too high | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `ID26` | PV overvoltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `ID27` | Bus voltage too high | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `ID29` | Bus voltage too low | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `ID41` | Relay check fault | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `ID42` | Insulation resistance low (fault) | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `ID43` | PE connection abnormal | fault | insulation | ตรวจสายดิน PE ของ inverter |
| `ID50` | Inverter overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `ID53` | Leakage current sensor fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `ID56` | Battery overvoltage | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `ID57` | Battery undervoltage | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `ID58` | BMS communication fault | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `ID60` | Backup overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `ID70` | Grid overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `ID82` | Meter communication fault | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `ID84` | Arc fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `_default` | Sofar fault | warning |  | ดู ID code บนหน้าจอหรือ SolarMAN แล้วเทียบตารางในคู่มือ Sofar |

## solax

| code | name | severity | category | action |
|---|---|---|---|---|
| `IE01` (IE 01) | TZ protect (hardware protection) | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `IE02` (IE 02) | Grid lost | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `IE03` (IE 03) | Grid voltage fault | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `IE04` (IE 04) | Grid frequency fault | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `IE05` (IE 05) | PV voltage fault | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `IE06` (IE 06) | Bus voltage fault | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `IE07` (IE 07) | Battery voltage fault | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `IE08` (IE 08) | AC 10-minute voltage fault | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `IE09` (IE 09) | DC injection overcurrent (DCI OCP) | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `IE10` (IE 10) | DC overvoltage (DCV OVP) | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `IE11` (IE 11) | Software overcurrent (SW OCP) | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `IE12` (IE 12) | Residual current overcurrent (RC OCP) | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `IE13` (IE 13) | Isolation fault | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `IE14` (IE 14) | Temperature over fault | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `IE15` (IE 15) | Battery connection direction fault | fault | battery_reverse | ปิดทุกอย่าง ตรวจขั้ว +/- ก่อนต่อใหม่ ตรวจว่าฟิวส์/เบรกเกอร์แบตยังดี |
| `IE16` (IE 16) | EPS overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `IE17` (IE 17) | EPS overvoltage | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `IE18` (IE 18) | Input overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `IE19` (IE 19) | EPS voltage low / battery low | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `IE20` (IE 20) | Internal communication fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `IE21` (IE 21) | Temperature sensor fault | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `IE25` (IE 25) | Internal communication fault (Inter com) | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `IE26` (IE 26) | Fan fault | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `IE28` (IE 28, BMS Lost) | BMS communication lost | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `IE29` (IE 29, Meter Fault) | Meter communication lost | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `IE30` (IE 30) | Battery fault (BMS) | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `IE32` (IE 32) | ARC fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `mode.3` | Run mode = Fault | fault | device_fault | ดู IE code ในหน้าจอ/SolaXCloud เพื่อรหัสจริง |
| `mode.4` | Run mode = Permanent fault | fault | device_fault | fault ถาวร ต้องปิดเปิดเครื่องหรือเคลม ดู IE code ประกอบ |
| `_default` | SolaX fault | warning |  | อ่านรหัส IE บนหน้าจอ/SolaXCloud แล้วเทียบตารางในคู่มือ |

## goodwe

| code | name | severity | category | action |
|---|---|---|---|---|
| `Utility Loss` | Utility loss | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `Vac Failure` (Vac Fail, AC V Outrange) | AC voltage out of range | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `Fac Failure` (Fac Fail, AC F Outrange) | AC frequency out of range | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `Utility Phase Failure` | Utility phase failure | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `PV Over Voltage` (PV Overvoltage) | PV overvoltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `Isolation Failure` (Isolation Fail, ISO Failure) | Isolation failure | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `Ground I Failure` (Ground Current Failure) | Ground current failure | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `GFCI Device Check Failure` (GFCI Device Failure) | GFCI device check failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `GFCI Consistency Failure` | GFCI consistency failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `GFCI Failure` | GFCI failure | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `Relay Check Failure` (Relay Failure) | Relay check failure | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `DC Injection High` (DCI High) | DC injection high | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `DCI Consistency Failure` | DCI consistency failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `Over Temperature` (Overtemperature, OverTemperature) | Over temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `Internal Fan Failure` (Fan Failure) | Internal fan failure | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `Bus Voltage Failure` (BUS Voltage Failure) | Bus voltage failure | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `AC HCT Check Failure` (AC HCT Failure) | AC current sensor check failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `External Flash Failure` | External flash failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `EEPROM R/W Failure` | EEPROM read/write failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `Back-Up Over Load` (Backup Overload, Back-up Overload) | Backup overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `Battery Communication Failure` (BMS Comm Fail, Battery Comm Fail) | BMS communication failure | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `Meter Communication Failure` (Meter Comm Fail) | Meter communication failure | warning | meter_comm | ตรวจสาย A/B ของ RS485 ที่มิเตอร์ ตั้ง address และ baud ตามคู่มือ ตรวจทิศ CT (ลูกศรชี้ไปทางกริด) ถ้ามิเตอร์หายจะทำให้ zero-export ไม่ทำงาน |
| `ARC Fault` (Arc Fault) | ARC fault | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `_default` | GoodWe error | warning |  | ดู error text ใน SEMS Portal > Alarm หรือ error_codes จาก inverter |

## sunspec

| code | name | severity | category | action |
|---|---|---|---|---|
| `Evt1.b0` | Ground fault | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `Evt1.b1` | DC over voltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `Evt1.b2` | AC disconnect open | warning | grid_loss | สวิตช์/เบรกเกอร์ AC เปิดอยู่ ตรวจ AC disconnect |
| `Evt1.b3` | DC disconnect open | info | pv_low | DC switch เปิดอยู่ ปิดสวิตช์ DC |
| `Evt1.b4` | Grid disconnect | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `Evt1.b5` | Cabinet open | info | config | ฝาเครื่อง/ตู้เปิดอยู่ ปิดฝาให้สนิท |
| `Evt1.b6` | Manual shutdown | info | config | มีคนสั่งปิดจากปุ่ม/แอป เปิดใหม่เมื่อพร้อม |
| `Evt1.b7` | Over temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `Evt1.b8` | Over frequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `Evt1.b9` | Under frequency | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `Evt1.b10` | AC over voltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `Evt1.b11` | AC under voltage | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `Evt1.b12` | Blown string fuse | warning | string_abnormal | ตรวจฟิวส์ DC ในกล่อง combiner/ใน inverter เปลี่ยนฟิวส์ค่าเดิม และหาสาเหตุ (string ขนานผิด |
| `Evt1.b13` | Under temperature | info | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `Evt1.b14` | Memory loss | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `Evt1.b15` | Hardware test failure | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `St.7` | Inverter state = Fault | fault | device_fault | อ่าน vendor event (EvtVnd) หรือรหัสจากหน้าจอผู้ผลิต |
| `_default` | SunSpec vendor event | warning |  | ดูรหัสจากหน้าจอ/แอปผู้ผลิต (EvtVnd เป็น bitfield เฉพาะยี่ห้อ) |

## solaredge

| code | name | severity | category | action |
|---|---|---|---|---|
| `18x38` (Vac Max, AC Voltage Too High) | AC voltage too high (Vac max) | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `18x37` (Vac Min, AC Voltage Too Low) | AC voltage too low (Vac min) | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `18x75` (Temperature Too High) | Temperature too high | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `18x86` (Isolation Fault, RISO, 03x9a, 3x9a) | Isolation fault | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `18x3D` (Ground Current, RCD) | Ground current too high | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `18xC` (Arc Fault, AFCI) | Arc fault detected | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `18xA8` (18xA6, 18xA7, 18xAA, Hardware Error) | Hardware error | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `DC Voltage Too High` | DC voltage too high | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `Fac Max` (Fac Min, AC Frequency) | AC frequency too high | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `Islanding` | Islanding detected | warning | islanding | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `Optimizer` (P_OK, Optimiser) | Optimizer communication / P_OK error | warning | optimizer | ดูแผงที่หายจากแผนผังในแอป ตรวจคอนเนกเตอร์และตัว optimizer ตัวนั้น |
| `Battery` (Battery Not Communicating, Lockout) | Battery not communicating / lockout | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `Backup Overload` | Backup overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `_default` | SolarEdge error | warning |  | อ่านรหัสจาก SetApp/monitoring portal (Error XXxYY) แล้วเทียบเอกสาร "Troubleshooting SolarEdge Systems" |

## fronius

| code | name | severity | category | action |
|---|---|---|---|---|
| `102` | AC voltage too high | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `103` | AC voltage too low | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `105` | AC frequency too high | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `106` | AC frequency too low | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `107` | AC grid outside permissible limits | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `108` | Stand-alone (islanding) operation detected | warning | islanding | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `112` | RCMU error (residual current) | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `240` (241, 242) | Arc detection triggered | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `301` | Overcurrent AC | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `302` | Overcurrent DC | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `303` | DC-DC overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `304` | Interior overtemperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `306` | Power low (PV insufficient) | info | pv_low | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `307` | DC low | info | pv_low | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `308` | Intermediate circuit voltage too high | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `309` (313) | Input voltage MPPT1 too high | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `311` | Polarity of DC strings reversed | fault | dc_reverse | ปิด DC switch วัดขั้วทุก string ด้วยมิเตอร์ แล้วสลับสายให้ถูก |
| `325` | Overtemperature in connection area | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `326` (327) | Fan 1 error | warning | fan | ปิดเครื่อง ทำความสะอาดพัดลม ถ้าไม่หมุนให้เปลี่ยนพัดลม (อะไหล่จากผู้ผลิต) |
| `401` | No communication with power stage set | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `408` | DC feed-in detected | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `443` | Intermediate circuit voltage too low or asymmetric | fault | bus | ตรวจ Voc ของ string และการต่อสาย DC ปิดเปิดใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `447` | Insulation error | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `448` | Neutral conductor not connected | warning | grid_loss | สาย N ไม่ต่อหรือหลุด ตรวจขั้ว N ที่ inverter |
| `457` | Grid relay sticking or N-PE voltage too high | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `463` | AC polarity reversed | warning | config | สลับ L/N ที่ขั้ว AC |
| `474` | RCMU sensor faulty | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `475` | Solar panel ground fault / insulation fault | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `502` | Insulation error on solar panels | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `509` | No energy fed into grid in past 24 hours | info | pv_low | ตรวจว่า DC switch เปิด แผงไม่โดนบัง หรือ inverter ค้าง |
| `515` | No communication with filter | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `516` | No communication with storage unit | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `517` | Power derating caused by high temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `522` (523) | DC low string 1 | info | pv_low | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `560` | Derating caused by over-frequency | info | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `567` | Grid voltage dependent power reduction active | info | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `607` | RCMU error | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `751` (752, 753) | Time lost (RTC) | info | firmware | ตั้งเวลาใหม่ใน web UI ถ้าเกิดซ้ำแบตเตอรี่ RTC หมด |
| `_default` | Fronius state code | warning |  | เทียบ state code กับตารางในคู่มือ Fronius (100 = grid |

## sma

| code | name | severity | category | action |
|---|---|---|---|---|
| `101` (102, 103) | Grid fault (voltage) | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `202` (203, 205, 206) | Grid fault (undervoltage / overvoltage) | warning | grid_undervoltage | วัดแรงดันกริดทุกเฟส ตรวจจุดต่อสายและเบรกเกอร์ ถ้าแรงดันจากการไฟฟ้าต่ำจริงให้แจ้งการไฟฟ้า |
| `301` | Grid fault 10-min average overvoltage | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `401` (404) | Grid fault (stand-alone / islanding) | warning | islanding | ปกติจะต่อกริดใหม่เองเมื่อกริดปกติ ถ้าเกิดบ่อยทั้งที่กริดปกติ ให้ตรวจสาย AC และ grid code ที่ตั้ง |
| `501` (507) | Grid fault (frequency) | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `601` | High DC component in grid current | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `701` | Frequency not permitted | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `901` | PE connection missing | fault | insulation | ต่อสาย PE ให้ครบ |
| `1001` | L and N swapped | warning | config | สลับสาย L/N ที่ขั้ว AC |
| `1302` | Waiting for grid voltage | info | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `1501` | Reconnection fault grid | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `3401` (3402, 3407) | DC overvoltage | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `3501` | Insulation failure | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `3601` | High discharge current | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `3701` | Residual current too high | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `3801` (3802) | DC overcurrent | fault | overcurrent | ตรวจว่า string ขนานไม่เกิน Isc ที่ inverter รับได้ ลดโหลดฝั่ง backup ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `3901` (3902) | Waiting for DC start conditions | info | pv_low | ถ้าเกิดเฉพาะเช้า-เย็นเป็นปกติ ถ้าเกิดกลางวันให้ตรวจ DC switch ฟิวส์ และคอนเนกเตอร์ |
| `6002` (6001, 6120, 6301, 6302, 6401, 6438) | Self-diagnosis > interference device | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `7002` | Sensor fault interior temperature | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `7702` (7701) | Device fault / power stage | fault | device_fault | ปิดเครื่องทั้ง AC/DC รอ 5 นาที เปิดใหม่ 1 ครั้ง ถ้ายังฟ้องให้จดรหัสและ serial แล้วเปิดเคลมกับผู้ผลิต อย่าซ่อมเอง |
| `7801` | Surge arrester error | fault | device_fault | ตรวจ SPD ภายในและเปลี่ยนโมดูลที่แสดงสีแดง |
| `8003` | Derating due to temperature | info | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `9002` | SMA Grid Guard code invalid | warning | config | ตรวจการตั้งค่าใน commissioning app ให้ตรงกับหน้างาน |
| `10108` | Time adjusted / old time | info | firmware | อัปเดต firmware ใหม่ผ่านแอปผู้ติดตั้ง หรือติดต่อผู้ผลิตเรื่อง license |
| `_default` | SMA event | warning |  | ดู event number ใน Sunny Portal/ennexOS แล้วเทียบตาราง "Event messages" ในคู่มือ |

## growatt

| code | name | severity | category | action |
|---|---|---|---|---|
| `No AC Connection` (No Utility, Error 202) | No AC connection | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `AC V Outrange` (Error 300, Vac) | AC voltage out of range | warning | grid_overvoltage | วัดแรงดันกริดที่ขั้ว inverter เทียบ setting (ไทย 220/380 V ±10%) ถ้าเกิดเฉพาะช่วงผลิตสูง ให้ลดค่า impedance ของสาย AC (เพิ่มขนาดสาย/ลดระยะ) หรือเปิดฟังก์ชัน Volt-Watt/Q(U) ตามข้อกำหนดการไฟฟ้า อย่าปรับ protection limit เกินที่การไฟฟ้าอนุญาต |
| `AC F Outrange` (Error 301) | AC frequency out of range | warning | grid_frequency | ถ้าเกิดชั่วคราวและกลับมาเองไม่ต้องทำอะไร ถ้าเกิดซ้ำให้ตรวจ grid code ที่ตั้งใน inverter และตรวจว่าจ่ายไฟจากเจนเนอเรเตอร์หรือไม่ |
| `PV Isolation Low` (Error 203, ISO) | PV isolation low | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `Residual I High` (Error 201, GFCI) | Residual current high | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `Output High DCI` (Error 209) | Output DC injection high | fault | dc_injection | ปิดเปิดเครื่องใหม่ ถ้าเกิดซ้ำติดต่อผู้ผลิต |
| `PV Voltage High` (Error 200) | PV voltage high | fault | dc_overvoltage | วัด Voc ของ string ตอนเช้า เทียบกับ Max DC voltage ของ inverter ถ้าเกินให้ลดจำนวนแผงต่อ string ห้ามเปิดเครื่องซ้ำจนกว่าจะแก้ |
| `Over Temperature` (NTC, Error 302) | Over temperature | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `Auto Test Failed` | Auto test failed | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `BMS COM Fault` (Battery Comm, Error 411) | BMS communication fault | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `Bat Voltage High` (Bat Voltage Low) | Battery voltage high | fault | battery | ดูรหัสของ BMS ในแอป ตรวจเบรกเกอร์แบตเตอรี่และขั้วต่อ ถ้า SOC ต่ำมากให้ปล่อยชาร์จจากกริด ถ้าเป็นแรงดันเซลล์ผิดปกติให้ติดต่อผู้ผลิตแบตเตอรี่ |
| `Overload` (Error 408) | EPS overload | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `Relay Fault` (Error 401) | Relay fault | fault | relay | ปิดเปิดเครื่องใหม่ 1 ครั้ง ถ้ายังฟ้องเป็นความเสียหายภายใน ติดต่อผู้ผลิตเคลม |
| `_default` | Growatt fault | warning |  | ดู fault/error number ใน ShineServer แล้วเทียบตารางในคู่มือ |

## sigen

| code | name | severity | category | action |
|---|---|---|---|---|
| `1001` | Sigen alarm 1001 (see Error Code List) | fault | device_fault | เปิดหน้า Error Code List ใน developer.sigencloud.com (บัญชี vendor) เพื่อความหมายและวิธีแก้ของรหัสนี้ |
| `plant.fault` | Plant running state = fault | fault | device_fault | ดู alarm ในแอป mySigen / Sigen Cloud เพื่อรหัสจริงของ inverter หรือแบตเตอรี่ |
| `_default` | Sigen alarm | warning |  | ดูรหัสในแอป mySigen หรือ Sigen Cloud > Alarm และเพิ่มลงตารางนี้เมื่อทราบความหมาย |

## solarman

| code | name | severity | category | action |
|---|---|---|---|---|
| `Grid Loss` (F35, No Grid) | No AC grid (F35) | warning | grid_loss | ตรวจว่ากริดมีไฟหรือไม่ วัดแรงดันที่ขั้ว AC ของ inverter ตรวจเบรกเกอร์ AC และจุดต่อสาย ถ้ากริดมีไฟแต่ยังฟ้อง ให้ตรวจสาย N ขาดหรือ RCD ตัด |
| `GFCI` (F16, F23, Leakage) | Leakage current (F16/F23) | fault | leakage | ตรวจฉนวนสาย DC และการต่อดินของโครงแผง ถ้าเกิดตอนฝนตกแล้วหายเป็นเรื่อง capacitance ปกติของ array ใหญ่ ถ้าเกิดถาวรให้ตรวจ AC wiring และ RCD ห้าม bypass sensor |
| `Insulation` (F24, ISO) | DC insulation (F24) | fault | insulation | ปิดเครื่อง วัดค่าฉนวน (Riso) ของแต่ละ string เทียบดิน ด้วย insulation tester 1000 V ต้อง > 1 MΩ ถ้าเกิดเฉพาะตอนเช้าชื้นแล้วหาย ให้ตรวจกล่อง junction/MC4 ที่มีน้ำเข้า ค่าที่ต่ำถาวรให้ไล่หาสายที่ถลอกหรือแผงรั่ว |
| `BMS` (F58) | BMS communication (F58) | fault | battery_comm | ตรวจสาย comm ขั้วต่อ pinout ตามคู่มือแบตเตอรี่รุ่นนั้น ตั้งค่า battery brand/protocol ใน inverter ให้ตรง เปิดแบตก่อนเปิด inverter |
| `Arc` (F63) | Arc fault (F63) | fault | arc | ห้าม reset ซ้ำโดยไม่ตรวจ ปิด DC switch แล้วตรวจ MC4 ทุกจุด สายที่ร้อน/ดำ ขั้วต่อใน inverter และกล่อง combiner ถ้าเป็น false alarm ซ้ำให้ทดสอบ AFCI self-test และอัปเดต firmware |
| `Temperature` (F64) | Heat sink temperature (F64) | warning | overtemp | ตรวจว่า inverter ไม่โดนแดดตรง มีระยะห่างตามคู่มือ ทำความสะอาดครีบระบายความร้อนและพัดลม ถ้า derating ตอนบ่ายเป็นประจำให้เพิ่มการระบายอากาศหรือย้ายตำแหน่ง |
| `Overload` (F34) | AC overload (F34) | warning | overload | ลดโหลดในวงจร backup ให้ต่ำกว่าพิกัด ย้ายมอเตอร์/แอร์ใหญ่ออกจากวงจร backup |
| `_default` | Solarman alert | warning |  | เปิด SolarMAN/Deye Cloud > Alerts ดู F-code หรือ ID code แล้วเทียบตาราง deye / sofar |

