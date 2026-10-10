"""
Unit and integration tests for multi-layer chat verification and auto-retry in LineSender
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import win32con

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.sender import LineSender, SendResult
from app.core.preflight import PreflightReport


class TestSenderVerification(unittest.TestCase):
    """ทดสอบระบบตรวจสอบชื่อห้องแชท 3 ชั้น และระบบตัดวงจร/ทำซ้ำอัตโนมัติ"""

    def setUp(self):
        self.sender = LineSender()

    def test_01_verify_chat_window_rules(self):
        """ทดสอบกฎการตรวจสอบชื่อหน้าต่างแชท _verify_chat_window"""
        with patch("win32gui.IsWindow", return_value=True):
            # 1. ชื่อตรงเป๊ะ
            with patch("win32gui.GetWindowText", return_value="test-bot"):
                self.assertTrue(self.sender._verify_chat_window(12345, "test-bot"))
                self.assertTrue(self.sender._verify_chat_window(12345, "TEST-BOT"))

            # 2. ชื่อเป็น Substring (เช่น กลุ่มมีจำนวนสมาชิก)
            with patch("win32gui.GetWindowText", return_value="ทีมพัฒนา (15)"):
                self.assertTrue(self.sender._verify_chat_window(12345, "ทีมพัฒนา"))

            # 3. ชื่อไม่ตรง (Mismatch) -> ต้องได้ False
            with patch("win32gui.GetWindowText", return_value="คุณสมชาย"):
                self.assertFalse(self.sender._verify_chat_window(12345, "test-bot"))

            # 4. หน้าต่างหลัก LINE (Title='LINE') -> ต้องได้ False (ไม่ให้ส่งเข้าหน้าต่างหลักที่ยังไม่แยก)
            with patch("win32gui.GetWindowText", return_value="LINE"):
                self.assertFalse(self.sender._verify_chat_window(12345, "test-bot"))

            # 5. ชื่อว่างเปล่า -> ต้องได้ False
            with patch("win32gui.GetWindowText", return_value=""):
                self.assertFalse(self.sender._verify_chat_window(12345, "test-bot"))

    def test_02_circuit_breaker_aborts_on_mismatch(self):
        """ทดสอบว่าหากชื่อหน้าต่างไม่ตรง Circuit Breaker จะตัดวงจรทันที ไม่มีการพิมพ์หรือส่งข้อความ"""
        mock_preflight = PreflightReport(
            is_ready=True,
            line_running=True,
            session_unlocked=True,
            target_window_found=True,
            target_hwnd=9999,
            target_title="Wrong Friend Name",
            main_window_hwnd=1111,
            can_auto_open=False,
            open_chats=["Wrong Friend Name"],
            errors=[]
        )

        with patch("app.core.sender.run_preflight_check", return_value=mock_preflight), \
             patch("win32gui.IsWindow", return_value=True), \
             patch("win32gui.GetWindowText", return_value="Wrong Friend Name"), \
             patch("win32gui.PostMessage") as mock_post_msg, \
             patch.object(self.sender, "_send_via_uia") as mock_uia, \
             patch.object(self.sender, "_send_via_fallback") as mock_fallback, \
             patch.object(self.sender, "_open_chat_in_main_window", return_value=None):

            res = self.sender.send_message(
                chat_title="test-bot",
                message_text="ข้อความทดสอบความปลอดภัย",
                retry_count=2,
                retry_delay=0.1
            )

            # ผลลัพธ์ต้องล้มเหลวอย่างปลอดภัย
            self.assertFalse(res.success)
            # ต้องไม่มีการเรียก Engine ส่งข้อความใดๆ ทั้งสิ้น
            mock_uia.assert_not_called()
            mock_fallback.assert_not_called()
            # ต้องส่งคำสั่งปิดหน้าต่างที่ผิด (WM_CLOSE = 0x0010)
            mock_post_msg.assert_any_call(9999, win32con.WM_CLOSE, 0, 0)

    def test_03_retry_recovers_after_initial_mismatch(self):
        """ทดสอบว่าระบบทำซ้ำอัตโนมัติ (Retry) จะปิดห้องผิดในรอบแรก แล้วสำเร็จในรอบสอง"""
        mock_preflight = PreflightReport(
            is_ready=True,
            line_running=True,
            session_unlocked=True,
            target_window_found=False,
            target_hwnd=None,
            target_title=None,
            main_window_hwnd=1111,
            can_auto_open=True,
            open_chats=[],
            errors=[]
        )

        # รอบ 1: คืนค่า None (เปิดผิดห้องหรือค้นหายังไม่เจอ)
        # รอบ 2: คืนค่า HWND 8888 (เปิดสำเร็จและยืนยันชื่อตรงแล้ว)
        search_mock_returns = [None, 8888]

        with patch("app.core.sender.run_preflight_check", return_value=mock_preflight), \
             patch.object(self.sender, "_open_chat_in_main_window", side_effect=search_mock_returns), \
             patch.object(self.sender, "_verify_chat_window", return_value=True), \
             patch.object(self.sender, "focus_window"), \
             patch.object(self.sender, "_send_via_uia", return_value=True) as mock_uia, \
             patch("win32gui.GetWindowText", return_value="test-bot"):

            res = self.sender.send_message(
                chat_title="test-bot",
                message_text="ข้อความทดสอบกู้คืนสำเร็จ",
                retry_count=3,
                retry_delay=0.1
            )

            # ต้องสำเร็จในรอบที่ 2
            self.assertTrue(res.success)
            self.assertEqual(res.attempts, 2)
            mock_uia.assert_called_once()


if __name__ == "__main__":
    unittest.main()

