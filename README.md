# Network Equipment Inventory System

ระบบจัดการคลังอุปกรณ์เครือข่ายผ่านหน้าจอ console (เมนูตัวเลือก) พัฒนาตามสเปก `AGENT.md`
ใช้ไฟล์ binary 3 ไฟล์ (`equipment.dat`, `category.dat`, `movement.dat`) อ่าน/เขียนด้วย
`struct` แบบ fixed-length record และสร้างรายงานเป็น `report.txt`

**ใช้เฉพาะ Standard Library ของ Python เท่านั้น** ไม่มี package ภายนอก ไม่ใช้ SQLite / JSON / pickle

---

## 1. ความต้องการระบบ

| รายการ | ค่า |
| --- | --- |
| Python | 3.10 ขึ้นไป (ทดสอบแล้วบน 3.14.6) |
| Package เพิ่มเติม | ไม่ต้องติดตั้ง |
| ระบบปฏิบัติการ | Windows / macOS / Linux |

---

## 2. เริ่มใช้งาน

```powershell
cd "D:\kmutnb\วิชาเรียน\ComPro 060233115 (S.2)\termproject\project-a"
python main.py
```

ครั้งแรกที่รัน โปรแกรมจะสร้างโฟลเดอร์ `data/` และไฟล์ binary ทั้ง 3 ไฟล์ให้เอง
(พร้อม category เริ่มต้น 5 รายการ) แล้วจะแสดงสรุปสถานะไฟล์และผลตรวจความถูกต้องก่อนเข้าเมนู

### ตัวเลือกตอนรัน

| คำสั่ง | ความหมาย |
| --- | --- |
| `python main.py` | เปิดโปรแกรมตามปกติ |
| `python main.py --seed 50` | สร้างข้อมูลตัวอย่าง 50 รายการก่อนเข้าเมนู (ใช้ทดลอง/สาธิต) |
| `python main.py --base-dir D:\mydata` | ใช้ `D:\mydata\data\` และ `D:\mydata\report.txt` แทน (โฟลเดอร์จะถูกสร้างให้) |
| `python main.py --help` | ดูตัวเลือกทั้งหมด |
| `python -m unittest discover -s tests -t .` | รันชุดทดสอบ 135 เคส |

> ปิดโปรแกรมด้วยเมนู `0. Exit` เสมอ เพื่อให้ข้อมูลถูก flush + `fsync` ลงดิสก์อย่างปลอดภัย

---

## 3. เมนูหลัก

```
========================================
 Network Equipment Inventory System
========================================

  1. Add Equipment
  2. Update Equipment
  3. Delete Equipment
  4. View
  5. Generate Report
  0. Exit

  Select:
```

| ตัวเลือก | การทำงาน |
| --- | --- |
| `1. Add Equipment` | เพิ่มอุปกรณ์ใหม่ 1 รายการ |
| `2. Update Equipment` | แก้ไขข้อมูลอุปกรณ์ที่มีอยู่ (แก้เฉพาะฟิลด์ที่ต้องการ) |
| `3. Delete Equipment` | ลบอุปกรณ์ (ยืนยันด้วย `y`/`n`) |
| `4. View` | เมนูย่อย: ดู 1 ราย / ดูทั้งหมด / กรอง / สถิติ |
| `5. Generate Report` | สร้าง `report.txt` ใหม่ |
| `0. Exit` | ปิดโปรแกรมอย่างปลอดภัย |

### เมนูย่อย View (`4`)

| ตัวเลือก | การทำงาน |
| --- | --- |
| `1. View One Equipment` | ดูรายละเอียดอุปกรณ์ 1 รายการ (บันทึกลง `movement.dat` เป็น op `VIEW`) |
| `2. View All Equipment` | ดูทุกรายการทีละ **10 แถว** — กด `Enter` เพื่อไปหน้าถัดไป, กด `q` เพื่อหยุด |
| `3. Filter Equipment` | กรองตามเกณฑ์ (ดูหัวข้อ 4.5) |
| `4. Statistics` | สรุปจำนวนตามสถานะ/หมวด/สถานที่ + มูลค่ารวม + ราคาเฉลี่ย |
| `0. Back` | กลับเมนูหลัก |

---

## 4. วิธีใช้ทีละคำสั่ง

### 4.1 เพิ่มอุปกรณ์ (`1`)

โปรแกรมจะถามทีละบรรทัด ตัวอย่างคำตอบ:

```
  Select: 1
  Equipment ID : 2001          <- ใส่ 0 เพื่อยกเลิกการเพิ่ม
  Category ID  : 3             <- ต้องเป็นหมวดที่มีอยู่ (ดูรายการที่แสดงด้านบน)
  Hostname     : FW-EDGE-01
  Brand        : Fortinet
  Model        : FG-100F
  Serial No    : FGT00001
  Location     : Building 3
  Status       : 1             <- 1=Active 2=Maintenance 3=Retired 4=Spare
  Price        : 45000.75
```

ผลลัพธ์:

```
  [OK] Equipment added.
  ...
  Stored in record slot 50 (reused free slot, offset 5824).
```

- ถ้าขึ้นว่า `newly appended slot` = เพิ่มต่อท้ายไฟล์
- ถ้าขึ้นว่า `reused free slot` = ใช้ช่องว่างที่เคยลบไป (โปรแกรมเลือก slot ต่ำสุดก่อนเสมอ)
- Equipment ID ที่มีอยู่แล้วจะถูกปฏิเสธและให้ใส่ใหม่

### 4.2 แก้ไขอุปกรณ์ (`2`)

```
  Select: 2
  Equipment ID : 2001
  Current values (press Enter to keep a field unchanged):
    ...
  Category ID  : 3          <- กด Enter = ใช้ค่าเดิม
  New Hostname     : FW-EDGE-01-NEW   <- กด Enter = ไม่เปลี่ยน
  New Brand        :
  New Model        :
  New Serial No    :
  New Location     :
  New Status       :
  New Price        :
```

**กด `Enter` เพื่อคงค่าเดิม** เฉพาะฟิลด์ที่ต้องการแก้จึงต้องพิมพ์ ถ้าไม่เปลี่ยนอะไรเลยจะขึ้น
`[i] Nothing changed.` และไม่เขียนทับไฟล์

### 4.3 ลบอุปกรณ์ (`3`)

```
  Select: 3
  Equipment ID : 2001
    (แสดงรายละเอียดก่อนลบ)
  Are you sure you want to delete equipment 2001? (y/n): y
  [OK] Equipment 2001 deleted.
  Record slot 50 stays in the file as a free slot and will be reused by the next add.
```

> ไฟล์ binary **ไม่หด** ข้อมูลเดิมยังอยู่ในไฟล์แต่ถูกทำเครื่องหมายสถานะ `0 = Deleted/Free`
> และ slot นั้นจะถูกใช้ซ้ำเมื่อเพิ่มรายการใหม่

### 4.4 ดูข้อมูล (`4`)

- **`4` → `1`** ดู 1 รายการ: ใส่ Equipment ID แล้วดูรายละเอียดทั้งหมด
- **`4` → `2`** ดูทั้งหมด: แสดงทีละ 10 แถว
  ```
    Press Enter for the next page, q to stop:
  ```
- **`4` → `4`** สถิติ: จำนวนแยกตามสถานะ, ตามหมวด, ตามสถานที่, มูลค่ารวม, ราคาเฉลี่ย, จำนวน free slot

### 4.5 กรองข้อมูล (`4` → `3`)

| ตัวเลือก | เกณฑ์ | ตัวอย่างคำตอบ |
| --- | --- | --- |
| `1` | หมวดหมู่ | `3` = Firewall |
| `2` | ยี่ห้อ (contains) | `Cisco` |
| `3` | สถานที่ (contains) | `Server Room` |
| `4` | สถานะ | `2` = Maintenance |
| `5` | Hostname (contains) | `SW-` |
| `0` | กลับ | |

ผลลัพธ์แสดงเป็นตาราง พร้อมบรรทัดสรุปเงื่อนไขที่ใช้ เช่น `Filter: brand=Cisco`

### 4.6 สร้างรายงาน (`5`)

เขียนไฟล์ `report.txt` ใหม่ทั้งไฟล์ (ทับของเดิม) ประกอบด้วย 6 หมวด:

1. **Summary** — จำนวนรวม, แยกตามสถานะ, free slots, record slots, มูลค่ารวม, ราคาเฉลี่ย
2. **Equipment by Category**
3. **Equipment by Status**
4. **Equipment by Location**
5. **Recent Activity** — 10 การทำงานล่าสุดจาก `movement.dat` (เก่าสุดขึ้นก่อน)
6. **Binary File Layout** — format, ขนาด record, จำนวน record และรายชื่อ field ของทุกไฟล์

### 4.7 ออกจากโปรแกรม (`0`)

```
  All data flushed and closed safely. Goodbye!
```

ขั้นตอนการปิด: เขียน header ใหม่ → `flush()` → `fsync()` → `close()` ทั้ง 3 ไฟล์

---

## 5. กฎการตรวจสอบข้อมูล (Input Validation)

| ฟิลด์ | กฎ | ข้อความเมื่อผิด |
| --- | --- | --- |
| Equipment ID | เลขจำนวนเต็ม `1`–`4,294,967,295`, ห้ามซ้ำ | `already exists` / `must be a positive number` |
| Category ID | ต้องมีอยู่ใน `category.dat` และเป็นหมวดที่ active | `category 9 does not exist (available: 1, 2, 3, 4, 5)` |
| Hostname | ASCII ไม่ว่าง, ยาว ≤ 20 | `This field is required` / ตัดให้เองถ้ายาวเกิน |
| Brand | ASCII ไม่ว่าง, ยาว ≤ 16 | เหมือนกัน |
| Model | ASCII ไม่ว่าง, ยาว ≤ 20 | เหมือนกัน |
| Serial No | ASCII ไม่ว่าง, ยาว ≤ 20 | เหมือนกัน |
| Location | ASCII ไม่ว่าง, ยาว ≤ 24 | เหมือนกัน |
| Status | `1`–`4` (ห้ามใช้ `0`) | `status 0 (Free) is reserved for deleted records` |
| Price | `0` – `999,999,999.99` | `price cannot be negative` |

พฤติกรรมเมื่อผิดพลาด

- แสดงข้อความ `[!] ...` แล้วถามใหม่ที่เดิม **ไม่ทำให้โปรแกรมพัง**
- ค่าที่กรอกเกินความยาว ระบบจะแจ้งและ**ตัดให้อัตโนมัติ** (พร้อมบอกค่าที่ถูกเก็บ)
- ใส่ผิดพลาดเกิน **10 ครั้ง** ต่อ 1 ค่า → ละทิ้งรายการนั้นและกลับเมนูก่อนหน้า
- รองรับการพิมพ์เลขทศนิยมแบบ `45,000.75` (ลูกน้ำคั่นพันถูกลบให้)
- อักขระภาษาไทย / emoji ใช้ไม่ได้ เพราะทุก text field เก็บเป็น ASCII ตามสเปก (ถ้าจำเป็นต้องแก้ encoding ใน `utils.py`)

---

## 6. ตารางรหัส

### สถานะอุปกรณ์ (Equipment Status)

| รหัส | ความหมาย |
| --- | --- |
| `0` | Deleted/Free (สงวนไว้ให้ระบบ ใช้เพิ่มเองตอนลบ) |
| `1` | Active |
| `2` | Maintenance |
| `3` | Retired |
| `4` | Spare |

### หมวดหมู่เริ่มต้น (Category)

| รหัส | ชื่อ | คำอธิบาย |
| --- | --- | --- |
| `1` | Switch | Layer 2 network access switch |
| `2` | Router | Layer 3 routing device |
| `3` | Firewall | Security gateway appliance |
| `4` | Access Point | Wireless access point |
| `5` | Server | Rack mounted network server |

### รหัสการทำงานที่บันทึกใน `movement.dat`

| รหัส | ความหมาย | บันทึกเมื่อ |
| --- | --- | --- |
| `1` | ADD | เพิ่มอุปกรณ์ |
| `2` | UPDATE | แก้ไขอุปกรณ์ |
| `3` | DELETE | ลบอุปกรณ์ |
| `4` | VIEW | เปิดดูรายละเอียด 1 รายการ |

---

## 7. ไฟล์ที่โปรแกรมสร้าง

| ไฟล์ | struct format | ขนาด/record | เนื้อหา |
| --- | --- | --- | --- |
| `data/equipment.dat` | `<II20s16s20s20s24sIf` | **116 bytes** | equipment_id, category_id, hostname, brand, model, serial_no, location, status, price |
| `data/category.dat` | `<I20s40sI` | **68 bytes** | category_id, category_name, description, status |
| `data/movement.dat` | `<QIII24sf` | **48 bytes** | timestamp, op_code, equipment_id, status_after, location_after, price_after |
| `report.txt` | — | — | รายงานข้อความ (UTF-8) ล่าสุดจากเมนู `5` |

**ทุก format เป็น Little-Endian (`<`)** และ text field เป็น ASCII เติมด้วย `b"\x00"` ท้ายฟิลด์

### โครงสร้างไฟล์

```
+---------------------------+-------------------------+-------------------------+ ...
| Header 24 bytes          | Record 0 (116 bytes)     | Record 1 (116 bytes)     |
+---------------------------+-------------------------+-------------------------+
```

Header ของทุกไฟล์ (24 bytes, `<8sHHIII`):

| ฟิลด์ | ขนาด | ความหมาย |
| --- | --- | --- |
| `magic` | 8 bytes | `NEQEQP01` / `NEQCAT01` / `NEQMOV01` |
| `version` | 2 bytes | เวอร์ชันโครงสร้างไฟล์ (ปัจจุบัน = 1) |
| `header_size` | 2 bytes | 24 |
| `record_size` | 2 bytes | 116 / 68 / 48 |
| `record_count` | 4 bytes | จำนวน record ทั้งหมด (รวมที่ถูกลบ) |
| `free_count` | 4 bytes | จำนวน slot ที่ถูกลบ/ว่าง |

**สูตรตำแหน่ง record:** `offset = 24 + (index × record_size)`
เช่น record slot 0 อยู่ที่ offset 24, slot 1 อยู่ที่ offset 140

ตัวอย่างข้อมูลจริง 8 ไบต์แรกของ record 0 ใน `equipment.dat`:

```
e9 03 00 00 01 00 00 00   ->  1001 (id), 1 (category)   [Little-Endian]
```

---

## 8. หลักการทำงานภายใน (สรุป)

- **Index อยู่ใน memory** — สร้างใหม่ทุกครั้งที่เปิดโปรแกรม โดยอ่าน `equipment.dat` ทั้งไฟล์
  จึงไม่มีไฟล์ index แยก (ใช้ไฟล์ binary 3 ไฟล์ตามสเปกพอดี)
- **Free slot reuse** — slot ที่ลบถูกเก็บไว้ในไฟล์ ระบบเลือกใช้ slot ที่ว่างค่าต่ำสุดก่อน
  ส่วนท้ายของไฟล์จะโตเฉพาะเมื่อไม่มี slot ว่าง
- **การเขียนทับข้อมูล** — ใช้ `seek(offset)` + `write()` เฉพาะ record ที่ต้องแก้ ไม่เขียนทับทั้งไฟล์
- **ความปลอดภัยของข้อมูล** — ทุกครั้งที่ปิดโปรแกรมจะเขียน header ใหม่ `flush()` และ `fsync()`
- **ตรวจจับไฟล์เสีย** — ตรวจ magic, version, header_size, record_size, จำนวน record และขนาดไฟล์จริง
  ถ้าไม่ถูกต้องจะ **ปิดไฟล์ทันทีโดยไม่เขียนทับข้อมูล** และแจ้งข้อความ (รหัสจบการทำงาน = 2)
- **`movement.dat` เป็น append-only** — เพิ่ม record ท้ายไฟล์ทุกครั้งที่มี ADD / UPDATE / DELETE / VIEW
  จึงเป็นประวัติการทำงานทั้งหมด (โตไม่จำกัด)
- **Ctrl+C / ปิด input** — จับ `EOFError` / `KeyboardInterrupt` แล้วปิดไฟล์อย่างปลอดภัยก่อนจบ

---

## 9. การทดสอบ

```powershell
python -m unittest discover -s tests -t .
```

ผลลัพธ์ปัจจุบัน: **135 tests ผ่านทั้งหมด (OK)** ครอบคลุม

- pack/unpack round-trip และขนาด record ที่คำนวณด้วย `struct.calcsize()`
- ไฟล์ว่าง / ไฟล์ไม่มี / header ผิด / record size ผิด / version ผิด / magic ผิด / record ถูกตัด
- ยืนยันว่าโปรแกรม **ไม่เขียนทับไฟล์ที่เสีย**
- index และ free list: สร้างใหม่, ตรวจสอบ, ใช้ slot ซ้ำ
- CRUD ครบวงจร, ID ซ้ำ, ID ไม่มีอยู่, ค่า boundary (0, ราคาสูงสุด, string ยาวเกิน)
- อินพุตผิดทุกแบบ (ตัวอักษรแทนตัวเลข, ติดลบ, เกินขอบเขต, ว่าง, เกิน ASCII)
- `movement.dat`, การสร้าง `report.txt`, สถิติ และการค้นหาด้วยทุกเกณฑ์
- สถานการณ์ 50+ รายการ + ปิด/เปิดใหม่ + ลบแล้วเพิ่มใหม่ใช้ slot เดิม
- ทุกเมนูผ่านการเรียก `Application.run()` แบบ end-to-end พร้อม input จำลอง

---

## 10. เมื่อพบปัญหา

| อาการ | วิธีแก้ |
| --- | --- |
| ขึ้นข้อความ `Corrupt file` / ไฟล์ถูกปฏิเสธ | ไฟล์เสียหรือถูกแก้ไข — สำรองไฟล์ไว้ก่อน แล้วลบ `data/*.dat` เพื่อเริ่มใหม่ |
| ข้อความภาษาไทยใน path แสดงเพี้ยน | โปรแกรมตั้ง console เป็น UTF-8 ให้แล้ว หากยังเพี้ยนให้รัน `chcp 65001` ใน PowerShell |
| อยากเริ่มข้อมูลใหม่ทั้งหมด | ปิดโปรแกรม แล้วลบโฟลเดอร์ `data/` (category เริ่มต้น 5 หมวดจะถูกสร้างใหม่เอง) |
| เพิ่มแล้ว ID ซ้ำ | ใช้เลขอื่น หรือแก้ไข/ลบ record เดิมก่อน |
| ต้องการทดลองโดยไม่กระทบข้อมูลเดิม | `python main.py --base-dir D:\temp-demo` |
| ข้อมูลเป็นภาษาไทย | ใช้ไม่ได้ตามสเปก (text field เป็น ASCII) ต้องแก้ `utils.py` ให้ encode เป็น UTF-8 และเพิ่มขนาด field |

---

## 11. ข้อจำกัดที่ทราบ

1. **`movement.dat` เก็บประวัติการทำงาน** (ADD/UPDATE/DELETE/VIEW) ไม่ใช่การย้ายเครื่องจริง
   ถ้าต้องการเป็น "การย้ายอุปกรณ์ระหว่างสถานที่" ต้องปรับ schema ใหม่
2. **`price` เก็บเป็น float32** จึงมีความคลาดเคลื่อนระดับ ~0.01 บาทในบางค่า
3. **Free Slots = จำนวน record ที่ถูกลบเสมอ** เพราะ slot ที่ลบถูก recycle ทันที
4. **`movement.dat` โตไม่จำกัด** (48 bytes ต่อการทำงานหนึ่งครั้ง)
5. **เป็นโปรแกรม console** ไม่มี GUI และไม่มีระบบผู้ใช้/รหัสผ่าน
6. **หน้าจอ View All / Filter** ต้องเลื่อนด้วยการกด Enter ทีละหน้า (ไม่ใช่ `less`)

---

## 12. โครงสร้างโปรเจกต์

| ไฟล์ | หน้าที่ |
| --- | --- |
| `main.py` | จุดเริ่มต้น, เมนูทั้งหมด, การรับอินพุต/แสดงผล, การปิดโปรแกรมอย่างปลอดภัย, ตัวเลือก CLI |
| `config.py` | path, struct format/ขนาด, magic, status/op code, ขนาด field, category เริ่มต้น |
| `models.py` | dataclass `Equipment` / `Category` / `Movement` + `to_bytes()` / `from_bytes()` |
| `storage.py` | อ่าน/เขียงไฟล์ binary, header, `seek()`, free list, ตรวจไฟล์เสีย, `flush`/`fsync` |
| `index.py` | index `equipment_id → record slot` (ค้นหาและตรวจสอบความถูกต้อง) |
| `database.py` | ครอบคลุม 3 ไฟล์ + index + category cache, เปิด/ปิดอย่างปลอดภัย |
| `validation.py` | ฟังก์ชันตรวจสอบอินพุตและค่าที่คอมโพเนนต์ลง binary |
| `crud.py` | ตรรกะ Add / Update / Delete / View / Filter / Statistics + บันทึก movement |
| `report.py` | สร้างเนื้อหา `report.txt` |
| `utils.py` | encode/decode ข้อความ ASCII, format ตัวเลข/เวลา, ตรวจ ASCII |
| `tests/test_system.py` | ชุดทดสอบ 135 เคส |
| `data/` | ไฟล์ binary ที่สร้างขึ้นตอนรันโปรแกรม |
| `report.txt` | รายงานล่าสุด |
| `AGENT.md` | ข้อกำหนดของโครงการ (ต้นฉบับ) |
