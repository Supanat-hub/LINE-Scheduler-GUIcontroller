"""
Test suite for Auto-Open preflight logic and routing
"""
import sys
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import app

from app.core.preflight import run_preflight_check


def test_auto_open_when_chat_window_open():
    """กรณีที่ 1: ผู้ใช้เปิดหน้าต่างแชทแยกไว้แล้ว -> ใช้หน้าต่างแยกโดยตรง"""
    fake_windows = [
        {"hwnd": 1001, "title": "LINE", "class": "Qt663QWindowIcon", "rect": (0, 0, 800, 600), "is_main": True, "is_minimized": False},
        {"hwnd": 1002, "title": "test-bot", "class": "Qt663QWindowIcon", "rect": (100, 100, 500, 500), "is_main": False, "is_minimized": False},
    ]
    with patch("app.core.preflight.is_session_locked", return_value=False), \
         patch("app.core.preflight.get_all_line_windows", return_value=fake_windows):
        report = run_preflight_check("test-bot")
        assert report.is_ready is True
        assert report.target_window_found is True
        assert report.target_hwnd == 1002
        assert report.can_auto_open is False
        print("[OK] Test 1 Passed: Chat window directly detected")


def test_auto_open_when_only_main_window_open():
    """กรณีที่ 2: ผู้ใช้ไม่ได้เปิดหน้าต่างแยกไว้ แต่เปิดหน้าต่างหลัก LINE -> รองรับ Auto-Open!"""
    fake_windows = [
        {"hwnd": 1001, "title": "LINE", "class": "Qt663QWindowIcon", "rect": (0, 0, 800, 600), "is_main": True, "is_minimized": False},
    ]
    with patch("app.core.preflight.is_session_locked", return_value=False), \
         patch("app.core.preflight.get_all_line_windows", return_value=fake_windows):
        report = run_preflight_check("test-bot")
        assert report.is_ready is True
        assert report.target_window_found is False
        assert report.main_window_hwnd == 1001
        assert report.can_auto_open is True
        print("[OK] Test 2 Passed: Auto-Open enabled when only main window is open")


def test_auto_open_when_no_line_windows():
    """กรณีที่ 3: ไม่ได้เปิด LINE เลย -> รายงานข้อผิดพลาดชัดเจน"""
    fake_windows = []
    with patch("app.core.preflight.is_session_locked", return_value=False), \
         patch("app.core.preflight.get_all_line_windows", return_value=fake_windows):
        report = run_preflight_check("test-bot")
        assert report.is_ready is False
        assert report.target_window_found is False
        assert report.can_auto_open is False
        assert len(report.errors) > 0
        print("[OK] Test 3 Passed: Error reported when LINE is not running")


def test_auto_open_when_line_in_tray():
    """กรณีที่ 4: LINE ซ่อนอยู่ในถาดระบบ (Tray) -> ตรวจพบและรองรับ Auto-Open พร้อมกู้คืน!"""
    fake_windows = [
        {"hwnd": 1001, "title": "LINE", "class": "Qt663QWindowIcon", "rect": (0, 0, 800, 600), "is_main": True, "is_minimized": False, "is_in_tray": True},
    ]
    with patch("app.core.preflight.is_session_locked", return_value=False), \
         patch("app.core.preflight.get_all_line_windows", return_value=fake_windows):
        report = run_preflight_check("test-bot")
        assert report.is_ready is True
        assert report.line_running is True
        assert report.target_window_found is False
        assert report.main_window_hwnd == 1001
        assert report.can_auto_open is True
        print("[OK] Test 4 Passed: Auto-Open enabled when LINE is in system tray")


if __name__ == "__main__":
    test_auto_open_when_chat_window_open()
    test_auto_open_when_only_main_window_open()
    test_auto_open_when_no_line_windows()
    test_auto_open_when_line_in_tray()
    print("\n[SUCCESS] All 4 Preflight Auto-Open Tests Passed 100%!")

