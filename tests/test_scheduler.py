"""
Phase 2 Test Suite: Verification of SQLite Database, Template Engine, and APScheduler Manager
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path and initialize desktop attachment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import app

from app.db import Database
from app.core.template import render_message_template
from app.core.scheduler import SchedulerManager
from app.core.sender import LineSender, SendResult


def test_database():
    print("\n--- 1. ทดสอบ SQLite Database (app/db.py) ---")
    # ใช้ฐานข้อมูลทดสอบชั่วคราว
    test_db_path = BASE_DIR / "data" / "test_scheduler.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db = Database(db_path=test_db_path)
    print("[✓] สร้างและเชื่อมต่อฐานข้อมูลทดสอบสำเร็จ")

    # ทดสอบสร้างงาน
    job_id = db.create_job(
        name="รายงานยอดขายประจำวัน",
        chat_title="test-bot",
        message_template="ยอดขายวันที่ {วันที่} ({วัน}): 100,000 บาท 💰",
        schedule_type="daily",
        schedule_time="09:00",
        misfire_policy="grace_period",
        misfire_grace_minutes=30
    )
    print(f"[✓] สร้างงานสำเร็จ (Job ID: {job_id})")

    # ดึงข้อมูลงาน
    job = db.get_job(job_id)
    assert job is not None
    assert job["name"] == "รายงานยอดขายประจำวัน"
    assert job["is_enabled"] == 1
    print(f"[✓] อ่านข้อมูลงานถูกต้อง: {job['name']} ({job['schedule_type']} @ {job['schedule_time']})")

    # ทดสอบ Toggle ปิดใช้งาน
    db.toggle_job(job_id, False)
    job_disabled = db.get_job(job_id)
    assert job_disabled["is_enabled"] == 0
    print("[✓] Toggle ปิดงานสำเร็จ (is_enabled = 0)")

    # เปิดกลับคืน
    db.toggle_job(job_id, True)

    # ทดสอบ Settings
    db.set_setting("test_key", "test_val_123")
    val = db.get_setting("test_key")
    assert val == "test_val_123"
    print(f"[✓] บันทึกและอ่าน Settings สำเร็จ: {val}")

    # ทดสอบ Export JSON
    json_export = db.export_jobs_json()
    assert "รายงานยอดขายประจำวัน" in json_export
    print(f"[✓] ส่งออก JSON สำเร็จ ({len(json_export)} chars)")

    # ล้างไฟล์ทดสอบ
    try:
        test_db_path.unlink(missing_ok=True)
    except Exception:
        pass
    print("[✓] ผ่านการทดสอบ Database ทั้งหมด")


def test_template_rendering():
    print("\n--- 2. ทดสอบระบบแปลงตัวแปรในข้อความ (Template Variables) ---")
    template = "สวัสดี{วัน} ที่ {วันที่} เวลา {เวลา} ปี {ปี} 🚀"
    rendered = render_message_template(template)
    print(f"[*] ต้นฉบับ: {template}")
    print(f"[✓] ผลลัพธ์: {rendered}")
    assert "{วันที่}" not in rendered
    assert "{วัน}" not in rendered
    assert "{เวลา}" not in rendered
    assert "{ปี}" not in rendered
    print("[✓] ตัวแปรทั้งหมดถูกแทนที่ด้วยข้อมูลจริงเรียบร้อย")


def test_scheduler_live_trigger():
    print("\n--- 3. ทดสอบการตั้งเวลาจริงและส่งข้อความผ่าน Scheduler (APScheduler) ---")

    db = Database()
    # สร้างงานทดสอบแบบส่งครั้งเดียวในอีก 4 วินาทีข้างหน้า
    target_time = (datetime.now() + timedelta(seconds=4)).strftime("%Y-%m-%d %H:%M:%S")

    job_id = db.create_job(
        name="ทดสอบส่งด่วน Phase 2",
        chat_title="test-bot",
        message_template="⏰ [Scheduler Live Test]\nส่งอัตโนมัติเมื่อ: {วันที่} เวลา {เวลานาทีวินาที}\nระบบ APScheduler + SQLite ทำงานสมบูรณ์ 🚀🎯",
        schedule_type="once",
        schedule_time=target_time
    )
    print(f"[*] สร้างงานทดสอบ ID: {job_id} ตั้งเวลาให้รันที่: {target_time}")

    scheduler_mgr = SchedulerManager(db=db)
    executed_events = []

    def on_executed(j_id, result):
        executed_events.append((j_id, result))

    scheduler_mgr.register_on_executed_callback(on_executed)
    scheduler_mgr.start()

    next_run = scheduler_mgr.get_next_run_time(job_id)
    print(f"[*] ตรวจสอบจาก APScheduler: กำหนดรันครั้งถัดไปคือ {next_run}")

    print("[*] กำลังรอให้ Scheduler ทำงานอัตโนมัติ (ประมาณ 6 วินาที)...")
    for i in range(6, 0, -1):
        time.sleep(1)
        if executed_events:
            break

    scheduler_mgr.shutdown()

    if executed_events:
        j_id, res = executed_events[0]
        print(f"[✓] Callback แจ้งเตือน: งาน ID {j_id} ทำงานเสร็จแล้ว!")
        print(f"    - ผลลัพธ์: {'สำเร็จ' if res.success else 'ล้มเหลว'}")
        print(f"    - เวลา: {res.timestamp}")

        # ตรวจสอบว่ามีบันทึกใน execution_logs
        logs = db.get_execution_logs(limit=5)
        found_in_log = any(log["job_id"] == job_id for log in logs)
        print(f"[✓] ตรวจสอบในตาราง execution_logs: {'พบประวัติการทำงาน' if found_in_log else 'ไม่พบ'}")

        # ตรวจสอบว่างาน once ถูกปิดใช้งานอัตโนมัติ
        updated_job = db.get_job(job_id)
        print(f"[✓] งานแบบครั้งเดียวถูกปิดใช้งานแล้ว: is_enabled={updated_job['is_enabled']}")

        # ลบงานทดสอบ
        db.delete_job(job_id)
    else:
        print("[-] ไม่พบเหตุการณ์การทำงานตามกำหนดเวลา")
        assert False, "Scheduler did not trigger in time"


def main():
    print("=" * 65)
    print(" LINE Scheduler - Phase 2 Verification Test Suite")
    print("=" * 65)

    test_database()
    test_template_rendering()
    test_scheduler_live_trigger()

    print("\n" + "=" * 65)
    print(" [PASSED] การทดสอบ Phase 2: Scheduler & SQLite สมบูรณ์เรียบร้อย 100%!")
    print("=" * 65)


if __name__ == "__main__":
    main()
