"""
Phase 1 Test Suite: Verification of Pre-flight, LineSender, Retry, and Logging
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path and initialize desktop attachment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import app

from app.core.logger import logger
from app.core.preflight import run_preflight_check, get_all_line_windows
from app.core.sender import LineSender
from app.config import LOGS_DIR, SCREENSHOTS_DIR


def test_phase_1():
    print("=" * 65)
    print(" LINE Scheduler - Phase 1 Verification Test Suite")
    print("=" * 65)

    # 1. ทดสอบการค้นหาหน้าต่างทั้งหมด
    print("\n--- 1. ทดสอบการสแกนหน้าต่าง LINE ทั้งหมด ---")
    all_wins = get_all_line_windows()
    print(f"[+] พบหน้าต่าง LINE ทั้งหมด: {len(all_wins)} หน้าต่าง")
    for w in all_wins:
        t_type = "หน้าต่างหลัก" if w['is_main'] else "หน้าต่างแชทแยก"
        print(f"    - [{t_type}] {w['title']!r} (HWND: {w['hwnd']})")

    # 2. ทดสอบ Pre-flight Check กับห้องจริง
    print("\n--- 2. ทดสอบ Pre-flight Check ---")
    chat_windows = [w for w in all_wins if not w['is_main']]
    if not chat_windows:
        print("[-] ไม่พบหน้าต่างแชทแยก กรุณาดับเบิลคลิกเปิดห้องแชทใน LINE ก่อนทดสอบ")
        return

    target_chat = chat_windows[0]['title']
    print(f"[*] ทดสอบ Pre-flight กับห้อง '{target_chat}':")
    report = run_preflight_check(target_chat)
    print(f"    - พร้อมทำงาน (is_ready): {report.is_ready}")
    print(f"    - LINE เปิดอยู่ (line_running): {report.line_running}")
    print(f"    - เซสชันปลดล็อก (session_unlocked): {report.session_unlocked}")
    print(f"    - พบห้องเป้าหมาย (target_window_found): {report.target_window_found} (HWND: {report.target_hwnd})")

    # 3. ทดสอบ Pre-flight Check กับห้องที่ไม่มีอยู่จริง
    print("\n[*] ทดสอบ Pre-flight กับห้องที่ไม่มีอยู่ ('NonExistentGroup123'):")
    bad_report = run_preflight_check("NonExistentGroup123")
    print(f"    - พร้อมทำงาน: {bad_report.is_ready} (คาดหวัง: False)")
    print(f"    - ข้อผิดพลาดที่รายงาน: {bad_report.errors}")

    # 4. ทดสอบส่งข้อความจริงผ่าน LineSender
    print("\n--- 3. ทดสอบการส่งข้อความผ่าน LineSender ---")
    sender = LineSender()

    test_message = (
        f"🚀 [LINE Scheduler Core - Phase 1 Passed]\n"
        f"ทดสอบระบบ Core Sender พร้อม Pre-flight Check & UIA Engine\n"
        f"เวลาส่ง: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"ความสมบูรณ์: ภาษาไทย วรรณยุกต์ สระอำ อีโมจิ ✅💯🎉"
    )

    result = sender.send_message(
        chat_title=target_chat,
        message_text=test_message,
        retry_count=1,
        retry_delay=2.0
    )

    print(f"\n[+] ผลลัพธ์การส่งข้อความ:")
    print(f"    - สถานะสำเร็จ (success): {result.success}")
    print(f"    - ห้องเป้าหมาย: {result.chat_title}")
    print(f"    - จำนวนรอบที่ใช้ (attempts): {result.attempts}")
    print(f"    - เวลา: {result.timestamp.strftime('%H:%M:%S')}")

    # 5. ตรวจสอบ Log File
    print("\n--- 4. ตรวจสอบไฟล์บันทึก Log ---")
    today_log = LOGS_DIR / f"{time.strftime('%Y-%m-%d')}.log"
    if today_log.exists():
        print(f"[✓] ตรวจพบไฟล์ Log: {today_log} (ขนาด: {today_log.stat().st_size} bytes)")
    else:
        print(f"[-] ไม่พบไฟล์ Log ใน {LOGS_DIR}")

    print("\n" + "=" * 65)
    if result.success and today_log.exists():
        print(" [PASSED] การทดสอบ Phase 1: Core Module สมบูรณ์เรียบร้อย 100%!")
    else:
        print(" [FAILED] การทดสอบ Phase 1 มีบางส่วนไม่ผ่าน")
    print("=" * 65)


if __name__ == "__main__":
    test_phase_1()
