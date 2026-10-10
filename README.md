# LINE Scheduler (GUI Automation)

โปรแกรมตั้งเวลาส่งข้อความเข้ากลุ่ม LINE หรือแชทส่วนตัวอัตโนมัติบนระบบปฏิบัติการ Windows โดยควบคุมแอป LINE Desktop จริงผ่านเทคโนโลยี Windows UI Automation (UIA) และ Win32 API 

[![Download Installer](https://img.shields.io/badge/Download-Installer%20(.exe)-2563EB?style=for-the-badge&logo=windows)](https://github.com/Supanat-hub/LINE-Scheduler-GUIcontroller/releases/download/v1.0.1/LineScheduler-Setup.exe)
[![Download Portable](https://img.shields.io/badge/Download-Portable%20(.zip)-10B981?style=for-the-badge&logo=archive)](https://github.com/Supanat-hub/LINE-Scheduler-GUIcontroller/releases/download/v1.0.1/LineScheduler-v1.0.1-Portable.zip)
[![Release v1.0.1](https://img.shields.io/badge/Release-v1.0.1-orange?style=for-the-badge)](https://github.com/Supanat-hub/LINE-Scheduler-GUIcontroller/releases/tag/v1.0.1)

---

## ดาวน์โหลดใช้งาน (Downloads)

* **[LineScheduler-Setup.exe](https://github.com/Supanat-hub/LINE-Scheduler-GUIcontroller/releases/download/v1.0.1/LineScheduler-Setup.exe)** (26.6 MB): ตัวติดตั้งมาตรฐาน (แนะนำ) พร้อมสร้าง Shortcut บนเดสก์ท็อปและเปิดทำงานพร้อม Windows
* **[LineScheduler-v1.0.1-Portable.zip](https://github.com/Supanat-hub/LINE-Scheduler-GUIcontroller/releases/download/v1.0.1/LineScheduler-v1.0.1-Portable.zip)** (37.4 MB): แบบพกพา แตกไฟล์แล้วเปิด `LineScheduler.exe` ใช้งานได้ทันทีไม่ต้องติดตั้ง

---

## คุณสมบัติเด่น (Features)

* **ระบบตรวจสอบชื่อห้องแชท 3 ชั้น (3-Layer Chat Verification)**: ป้องกันการส่งผิดห้อง 100% ด้วยการรอผลการค้นหานิ่ง, ข้ามแถบหมวดหมู่, และดีดห้องแชทออกเป็นหน้าต่างแยกเพื่อตรวจสอบชื่อจริงผ่าน Win32 API ก่อนพิมพ์และส่งข้อความ
* **ระบบทำซ้ำอัตโนมัติเมื่อเปิดห้องไม่ตรง (Auto-Retry with Circuit Breaker)**: หากเปิดไม่ตรง จะปิดหน้าต่างนั้นทิ้งทันที และทำซ้ำให้อัตโนมัติ (หากครบ 3 ครั้งแล้วไม่พบ จะตัดวงจรฉุกเฉินและไม่ส่งข้อความใดๆ)
* **ระบบปลุก LINE จากถาดระบบอัตโนมัติ (Tray Auto-Wake)**: แม้ปิดหน้าต่าง LINE ลงถาดระบบ (System Tray) ระบบจะส่งสัญญาณปลุกหน้าต่างหลักของ LINE ขึ้นมาและส่งข้อความให้อัตโนมัติ
* **ระบบ Auto-Open ห้องแชท**: ไม่จำเป็นต้องเปิดหน้าต่างแชทแยกทิ้งไว้ล่วงหน้า ระบบสามารถค้นหาและเปิดห้องแชทผ่านหน้าต่างหลักได้ทันที
* **ข้อยกเว้น Windows Defender ในคลิกเดียว**: มีปุ่มเพิ่มโฟลเดอร์โปรแกรมในรายการยกเว้นของ Windows Defender ป้องกัน Antivirus ลบไฟล์
* **Dual Automation Engine ที่เสถียรที่สุด**:
  * **Primary Engine (Direct UIA Injection)**: ตรวจจับคอนโทรล `AutoSuggestTextArea` ของ Qt โดยตรง และส่งข้อความผ่าน Win32 Message Loop (`PostMessage`) โดยไม่ต้องแย่งเมาส์และไม่ต้องแย่งคลิปบอร์ดของผู้ใช้
  * **Secondary Engine (Fallback)**: พิกัดสัมพัทธ์ + คลิปบอร์ด + `Ctrl+V` สำรองอัตโนมัติ
* **รองรับภาษาไทยและอีโมจิสมบูรณ์**: รองรับสระ วรรณยุกต์ การขึ้นหลายบรรทัด และ Emojis ครบถ้วน
* **ระบบตัวแปรในข้อความอัตโนมัติ**: รองรับตัวแปร `{วันที่}`, `{วัน}`, `{เวลา}`, `{เดือน}`, `{ปี}`
* **ระบบป้องกันเครื่องหลับ/พักหน้าจอ 3 ชั้น (Keep-Awake Layers)**:
  * **ชั้นที่ 1 (Runtime)**: เรียก Win32 `SetThreadExecutionState` ป้องกัน Sleep/จอดับตลอดเวลาที่โปรแกรมเปิดอยู่ (ไม่ต้องใช้สิทธิ์แอดมิน)
  * **ชั้นที่ 2 (System Power Plan)**: ปุ่มกดปรับแต่ง Power Plan ปิดการหลับเมื่อพับฝาโน้ตบุ๊ก (`LIDACTION = 0`) และปิด ScreenSaver (พร้อมปุ่มคืนค่าเดิมเสมอ)
  * **ชั้นที่ 3 (Auto-start)**: ตัวเลือกเปิดโปรแกรมพร้อมเปิดเครื่อง Windows (At log on)
* **การตั้งเวลารอบด้านด้วย APScheduler & SQLite**:
  * รองรับ: ครั้งเดียว (Once), ทุกวัน (Daily), เลือกวันในสัปดาห์ (Weekly), และช่วงเวลา (Interval)
  * ระบบนโยบายพลาดเวลา (`Misfire Grace Time`) ส่งย้อนหลังได้หากเพิ่งเปิดเครื่อง
* **ระบบเฝ้าระวังสุขภาพ (Health Monitor ทุก 1 นาที)**: ตรวจสอบสถานะการล็อกหน้าจอ และแจ้งเตือนทันทีหาก LINE หลุด
* **System Tray & ป้องกันการพิมพ์ชน**: ย่อเก็บในถาดระบบ และเปลี่ยนสีไอคอนตามสถานะ (เขียว/เหลือง/แดง)
* **First-Run Wizard 4 ขั้นตอน**: ช่วยให้ผู้ใช้ใหม่ตั้งค่าเครื่องและเลือกห้องแชทได้ในไม่กี่คลิก
* **UI สะอาดตาด้วย CustomTkinter**: ธีม Dark/Light ทันสมัย ไม่มี Emoji รบกวนสายตาในส่วนติดต่อผู้ใช้

---

## ข้อกำหนดระบบ (Prerequisites)

1. **ระบบปฏิบัติการ**: Windows 10 หรือ Windows 11 (64-bit)
2. **LINE Desktop**: ติดตั้งและเข้าสู่ระบบไว้เรียบร้อย
   * ในการตั้งค่าของ LINE: **Settings -> Chats -> Send message with: Enter**
3. **การเปิดห้องแชท**: ดับเบิลคลิกที่ห้องแชทเป้าหมาย (เช่น `Keep Memo` หรือกลุ่มงาน) เพื่อให้ห้องแชทแยกออกมาเป็นหน้าต่างเดี่ยว (Pop-out Window)

---

## โครงสร้างโปรเจกต์ (Project Structure)

```
LINE-Scheduler-GUIcontroller/
├─ app/
│  ├─ main.py                # จุดเริ่มต้นการทำงานหลัก (Main Entrypoint)
│  ├─ config.py              # กำหนดค่า Path และการตั้งค่าคงที่
│  ├─ db.py                  # ตัวจัดการฐานข้อมูล SQLite (Jobs, Logs, Settings)
│  ├─ core/
│  │  ├─ sender.py           # Engine การส่งข้อความ (UIA + Fallback + Retry)
│  │  ├─ scheduler.py        # ตัวจัดการตารางงาน (APScheduler)
│  │  ├─ preflight.py        # ตรวจสอบความพร้อมก่อนส่งและตรวจจับหน้าต่าง
│  │  ├─ power.py            # ระบบกันหลับ 3 ชั้น (Keep-Awake Layers 1-3)
│  │  ├─ health.py           # ตัวเฝ้าระวังสุขภาพระบบประจำนาที
│  │  ├─ template.py         # ตัวแปลงตัวแปรในข้อความ ({วันที่}, {วัน}, {เวลา})
│  │  └─ logger.py           # บันทึก Log และจับภาพหน้าจอตอนเกิดข้อผิดพลาด
│  └─ ui/
│     ├─ main_window.py      # หน้าต่างหลัก (ตารางงาน, ประวัติ, ตั้งค่า)
│     ├─ job_editor.py       # โมดัลเพิ่ม/แก้ไขงาน
│     ├─ wizard.py           # วิซาร์ดเริ่มต้นใช้งาน 4 ขั้นตอน
│     ├─ tray.py             # ตัวจัดการ System Tray
│     └─ icons.py            # ไอคอนสถานะสำหรับ System Tray
├─ assets/                   # ไอคอนแอปพลิเคชัน (.ico, .png)
├─ data/                     # ฐานข้อมูล Logs และ Screenshots (สร้างอัตโนมัติ)
├─ installer/
│  ├─ build.spec             # สคริปต์คอมไพล์ PyInstaller
│  ├─ setup.iss              # สคริปต์สร้างตัวติดตั้ง Inno Setup
│  └─ build.bat              # สคริปต์อัตโนมัติรันคอมไพล์
├─ tests/                    # ชุดทดสอบแต่ละ Phase
└─ README.md
```

---

## การเริ่มใช้งานสำหรับนักพัฒนา (Running from Source)

1. ติดตั้ง Python 3.11 ขึ้นไป
2. ติดตั้งแพ็กเกจที่จำเป็น:
   ```cmd
   pip install customtkinter pywinauto pyautogui pyperclip apscheduler pystray pillow pywin32
   ```
3. เริ่มต้นรันโปรแกรม:
   ```cmd
   python app/main.py
   ```

---

## การสร้างตัวติดตั้ง (Building Setup.exe)

รันสคริปต์คอมไพล์อัตโนมัติในโฟลเดอร์ `installer`:
```cmd
installer\build.bat
```
* **ผลลัพธ์ PyInstaller**: `dist\LineScheduler\` (โปรแกรม Standalone ใช้งานได้ทันที)
* **ผลลัพธ์ Inno Setup**: `dist\installer\LineScheduler-Setup.exe` (ตัวติดตั้งพร้อมใช้อย่างสมบูรณ์)

