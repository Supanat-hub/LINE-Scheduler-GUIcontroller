"""
Test cases for LINE system tray detection, auto-wake, and health checks
"""

import unittest
import time
import win32gui
import win32con

from app.core.preflight import (
    attach_to_default_desktop,
    get_all_line_windows,
    find_line_tray_window,
    wake_line_from_tray,
    run_preflight_check
)
from app.core.health import HealthMonitor


class TestTrayWake(unittest.TestCase):

    def setUp(self):
        attach_to_default_desktop()

    def test_01_find_tray_window(self):
        """ตรวจสอบว่าสามารถตรวจพบ QTrayIconMessageWindow ของ LINE ได้"""
        tray_hwnd = find_line_tray_window()
        self.assertIsNotNone(tray_hwnd, "ควรตรวจพบหน้าต่าง Tray ของ LINE")
        self.assertTrue(win32gui.IsWindow(tray_hwnd), "HWND ของ Tray ต้องเป็นหน้าต่างจริง")

    def test_02_wake_and_preflight(self):
        """ทดสอบการปิดลงถาดระบบและปลุกอัตโนมัติผ่าน preflight check"""
        # ปิดลงถาดระบบ
        wins = get_all_line_windows()
        for w in wins:
            if w['is_main']:
                win32gui.PostMessage(w['hwnd'], win32con.WM_CLOSE, 0, 0)
        time.sleep(1.0)

        # ตรวจสอบ Preflight: ควรปลุกขึ้นมาอัตโนมัติและพร้อมส่ง
        report = run_preflight_check("test-bot", auto_wake_tray=True)
        self.assertTrue(report.line_running, "LINE ต้องถูกตรวจพบว่าทำงานอยู่")
        self.assertTrue(report.is_ready, "ระบบต้องพร้อมส่ง (is_ready = True)")
        self.assertTrue(report.can_auto_open or report.target_window_found, "ต้องสามารถเปิดห้องแชทได้")

    def test_03_health_monitor_in_tray(self):
        """ทดสอบ HealthMonitor ว่ารายงานสถานะปกติเมื่อ LINE อยู่ในถาดระบบ"""
        # ปิดหน้าต่างทั้งหมดลงถาดระบบ
        wins = get_all_line_windows()
        for w in wins:
            win32gui.PostMessage(w['hwnd'], win32con.WM_CLOSE, 0, 0)
        time.sleep(1.0)

        monitor = HealthMonitor()
        status = monitor.check_now()
        self.assertTrue(status.line_running, "HealthMonitor ต้องพบว่า LINE ทำงานอยู่")
        self.assertTrue(status.in_tray, "HealthMonitor ต้องตรวจพบว่า LINE อยู่ในถาดระบบ")
        self.assertTrue(status.is_healthy, "HealthMonitor ต้องรายงานสถานะเป็น Healthy")


if __name__ == "__main__":
    unittest.main()

