"""
Phase 3 Test Suite: Verification of Keep-Awake (Layers 1-3) & Health Monitor
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path and initialize desktop attachment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import app

from app.core.power import (
    enable_runtime_keep_awake,
    disable_runtime_keep_awake,
    backup_current_power_settings,
    is_startup_enabled,
    POWER_BACKUP_FILE
)
from app.core.health import HealthMonitor, HealthStatus


def test_power_layers():
    print("\n--- 1. ทดสอบระบบ Keep-Awake (Layers 1-3) ---")

    # Layer 1
    print("[*] ทดสอบ Layer 1: Win32 SetThreadExecutionState...")
    res_enable = enable_runtime_keep_awake()
    assert res_enable is True
    print("[✓] Layer 1 เปิดใช้งานสำเร็จ (เครื่องและจอจะไม่หลับ)")

    res_disable = disable_runtime_keep_awake()
    assert res_disable is True
    print("[✓] Layer 1 คืนค่าปกติสำเร็จ")

    # Layer 2: สำรองข้อมูลเดิม
    print("\n[*] ทดสอบ Layer 2: สำรองค่าเดิมของระบบ (Registry / ScreenSaver)...")
    backup = backup_current_power_settings()
    assert POWER_BACKUP_FILE.exists()
    print(f"[✓] สำรองข้อมูลสำเร็จ: {backup}")
    print(f"[✓] ตรวจพบไฟล์สำรองที่: {POWER_BACKUP_FILE}")

    # Layer 3: ตรวจสอบสถานะ Startup
    print("\n[*] ทดสอบ Layer 3: ตรวจสอบ Registry Run Key (Auto-start)...")
    startup_state = is_startup_enabled()
    print(f"[✓] สถานะการเปิดพร้อม Windows ปัจจุบัน: {startup_state}")


def test_health_monitor():
    print("\n--- 2. ทดสอบระบบตรวจสุขภาพประจำนาที (Health Monitor) ---")

    monitor = HealthMonitor(interval_secs=2)
    print("[*] ทดสอบ check_now()...")
    status = monitor.check_now()

    print(f"    - สุขภาพระบบพร้อมทำงาน (is_healthy): {status.is_healthy}")
    print(f"    - LINE เปิดอยู่ (line_running): {status.line_running}")
    print(f"    - หน้าจอไม่ล็อก (session_unlocked): {status.session_unlocked}")
    print(f"    - ห้องแชทที่เปิดอยู่: {status.open_chats}")
    if status.warnings:
        print(f"    - ข้อความแจ้งเตือน: {status.warnings}")

    assert status.line_running is True
    assert status.session_unlocked is True

    print("\n[*] ทดสอบ Background Monitoring Thread (รัน 3 วินาที)...")
    callback_records = []
    monitor.register_callback(lambda s: callback_records.append(s))
    monitor.start()

    time.sleep(3)
    monitor.stop()

    print(f"[✓] Monitor ทำงานใน Background และส่ง Callback ทั้งหมด {len(callback_records)} ครั้ง")
    assert len(callback_records) >= 1
    print("[✓] ผ่านการทดสอบ Health Monitor เรียบร้อย")


def main():
    print("=" * 65)
    print(" LINE Scheduler - Phase 3 Verification Test Suite")
    print("=" * 65)

    test_power_layers()
    test_health_monitor()

    print("\n" + "=" * 65)
    print(" [PASSED] การทดสอบ Phase 3: Keep-Awake & Health Monitor สมบูรณ์ 100%!")
    print("=" * 65)


if __name__ == "__main__":
    main()

