"""
Core LINE message sender module with UIA direct injection, retry handling, and logging
"""

import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import ctypes
import win32gui
import win32con
import pyperclip
import pyautogui
from pywinauto import Desktop

from app.config import (
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SEC,
    POST_FOCUS_DELAY_SEC,
    POST_INPUT_DELAY_SEC,
    POST_SEND_DELAY_SEC
)
from app.core.logger import logger, capture_screenshot
from app.core.preflight import run_preflight_check, attach_to_default_desktop


@dataclass
class SendResult:
    """ผลลัพธ์การส่งข้อความ"""
    success: bool
    chat_title: str
    message_preview: str
    attempts: int
    timestamp: datetime
    error_message: Optional[str] = None
    screenshot_path: Optional[Path] = None


class LineSender:
    """คลาสหลักสำหรับส่งข้อความอัตโนมัติเข้าห้องแชท LINE Desktop"""

    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.2

    @staticmethod
    def focus_window(hwnd: int) -> None:
        """กู้คืนหน้าต่าง (Restore) และดึงขึ้นมาอยู่แถวหน้าสุด (Foreground) รองรับทั้งถูกย่อและซ่อนในถาดระบบ"""
        attach_to_default_desktop()

        if not win32gui.IsWindowVisible(hwnd):
            logger.info(f"หน้าต่าง (HWND: {hwnd}) ซ่อนอยู่ในถาดระบบ (Tray) -> กำลังกู้คืนหน้าต่างขึ้นมาแสดงผล...")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        elif win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # ปลดล็อก Foreground lock โดยส่งสัญญาณ Alt เล็กน้อย
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        win32gui.SetForegroundWindow(hwnd)
        time.sleep(POST_FOCUS_DELAY_SEC)

    def _send_via_uia(self, hwnd: int, message_text: str) -> bool:
        """Engine 1: ส่งข้อความด้วย Direct UIA Injection ตรงเข้า AutoSuggestTextArea"""
        d = Desktop(backend='uia')
        bot_win = d.window(handle=hwnd)
        edit = bot_win.child_window(class_name='AutoSuggestTextArea', control_type='Edit')
        elem = edit.wrapper_object()

        # วางข้อความลงในช่องพิมพ์
        elem.set_edit_text(message_text)
        time.sleep(POST_INPUT_DELAY_SEC)

        # ส่งสัญญาณเคาะ Enter
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        time.sleep(POST_SEND_DELAY_SEC)

        # ตรวจสอบว่าช่องพิมพ์ว่างแล้วหรือไม่
        if elem.get_value() == "":
            return True

        # ถ้ายังค้างอยู่ ให้ลองคลิกปุ่มส่ง (Send Button)
        try:
            input_panel = bot_win.child_window(class_name='MessageInputPanel')
            buttons = [b for b in input_panel.descendants() if 'Button' in b.class_name() or b.element_info.control_type == 'Button']
            if buttons:
                send_btn = buttons[-1]
                send_rect = send_btn.rectangle()
                btn_cx = (send_rect.left + send_rect.right) // 2
                btn_cy = (send_rect.top + send_rect.bottom) // 2
                l_param = win32gui.MAKELONG(btn_cx - bot_win.rectangle().left, btn_cy - bot_win.rectangle().top)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
                time.sleep(0.05)
                win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, l_param)
                time.sleep(POST_SEND_DELAY_SEC)

            return elem.get_value() == ""
        except Exception as e:
            logger.warning(f"คลิกปุ่มส่งไม่สำเร็จ: {e}")
            return False

    def _send_via_fallback(self, hwnd: int, message_text: str) -> bool:
        """Engine 2: ส่งข้อความด้วยคลิปบอร์ด + พิกัดสัมพัทธ์ + Ctrl+V (เมื่อ UIA ไม่ทำงาน)"""
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        click_x = left + int(width * 0.45)
        click_y = bottom - 50

        pyautogui.click(click_x, click_y)
        time.sleep(0.2)

        original_clipboard = None
        try:
            original_clipboard = pyperclip.paste()
        except Exception:
            pass

        try:
            pyperclip.copy(message_text)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(POST_SEND_DELAY_SEC)
            return True
        finally:
            if original_clipboard is not None:
                try:
                    pyperclip.copy(original_clipboard)
                except Exception:
                    pass

    def _open_chat_in_main_window(self, main_hwnd: int, chat_title: str) -> bool:
        """ค้นหาและเปิดห้องแชทในหน้าต่างหลักของ LINE โดยอัตโนมัติ (Auto-Open)"""
        try:
            self.focus_window(main_hwnd)
            time.sleep(0.3)
            d = Desktop(backend='uia')
            main_w = d.window(handle=main_hwnd)

            # ค้นหาช่องค้นหา (LcTextField)
            search_box = main_w.child_window(class_name='LcTextField', control_type='Edit')
            elem = search_box.wrapper_object()
            elem.set_edit_text(chat_title)
            time.sleep(0.5)

            # ส่งคำสั่งเลื่อนลงเพื่อไฮไลต์ผลลัพธ์แรก และกด Enter เพื่อเปิดแชท
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYDOWN, win32con.VK_DOWN, 0)
            time.sleep(0.05)
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYUP, win32con.VK_DOWN, 0)
            time.sleep(0.2)

            win32gui.PostMessage(main_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            time.sleep(0.05)
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
            time.sleep(0.5)

            # ตรวจสอบว่าช่องพิมพ์ AutoSuggestTextArea ปรากฏขึ้นในหน้าต่างหลักแล้วหรือไม่ (รอสูงสุด 2.5 วินาที)
            start_wait = time.time()
            while time.time() - start_wait < 2.5:
                for c in main_w.descendants():
                    if 'AutoSuggest' in c.class_name():
                        logger.info(f"ตรวจพบช่องพิมพ์ AutoSuggestTextArea ในหน้าต่างหลักสำหรับ '{chat_title}' เรียบร้อย")
                        return True
                time.sleep(0.3)

            logger.warning(f"ค้นหาห้อง '{chat_title}' ในหน้าต่างหลักแล้ว แต่ไม่พบช่องพิมพ์ข้อความ")
            return False
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเปิดแชทผ่านหน้าต่างหลัก: {e}")
            return False

    def send_message(
        self,
        chat_title: str,
        message_text: str,
        retry_count: int = DEFAULT_RETRY_COUNT,
        retry_delay: float = DEFAULT_RETRY_DELAY_SEC
    ) -> SendResult:
        """
        ส่งข้อความไปยังห้องแชทที่ระบุ รองรับทั้งหน้าต่างแชทแยก และเปิดอัตโนมัติผ่านหน้าต่างหลัก
        """
        preview = message_text[:40].replace("\n", " ") + ("..." if len(message_text) > 40 else "")
        logger.info(f"เริ่มส่งข้อความเข้าห้องแชท '{chat_title}' (ข้อความ: '{preview}')")

        last_error = "Unknown error"

        for attempt in range(1, retry_count + 1):
            logger.info(f"กำลังส่งรอบที่ {attempt}/{retry_count}...")

            # 1. Pre-flight Check
            report = run_preflight_check(chat_title)
            if not report.is_ready:
                last_error = "; ".join(report.errors)
                logger.warning(f"Pre-flight check รอบที่ {attempt} ไม่ผ่าน: {last_error}")
                if attempt < retry_count:
                    logger.info(f"รอ {retry_delay} วินาทีก่อนลองใหม่...")
                    time.sleep(retry_delay)
                continue

            # กำหนดหน้าต่างเป้าหมาย
            is_main_win = False
            if report.target_window_found and report.target_hwnd:
                hwnd = report.target_hwnd
                target_name = report.target_title or chat_title
            elif report.can_auto_open and report.main_window_hwnd:
                logger.info(f"ไม่พบหน้าต่างแยกสำหรับ '{chat_title}' -> เริ่มกระบวนการ Auto-Open ในหน้าต่างหลัก...")
                opened = self._open_chat_in_main_window(report.main_window_hwnd, chat_title)
                if not opened:
                    last_error = f"ไม่สามารถค้นหาหรือเปิดห้องแชท '{chat_title}' ในหน้าต่างหลักได้"
                    logger.warning(f"รอบที่ {attempt} ไม่สำเร็จ: {last_error}")
                    if attempt < retry_count:
                        time.sleep(retry_delay)
                    continue
                hwnd = report.main_window_hwnd
                target_name = chat_title
                is_main_win = True
            else:
                last_error = "; ".join(report.errors) if report.errors else "ไม่พบหน้าต่างเป้าหมาย"
                logger.warning(f"รอบที่ {attempt} ไม่ผ่าน: {last_error}")
                if attempt < retry_count:
                    time.sleep(retry_delay)
                continue

            try:
                # 2. ดึงหน้าต่างขึ้นมา
                self.focus_window(hwnd)

                # 3. ส่งข้อความด้วย Engine 1 (UIA)
                sent_ok = False
                try:
                    sent_ok = self._send_via_uia(hwnd, message_text)
                except Exception as e_uia:
                    logger.warning(f"Engine 1 (UIA) ล้มเหลว: {e_uia}")

                # 4. ถ้ายังไม่สำเร็จและไม่ใช่หน้าต่างหลัก ให้ลอง Fallback
                if not sent_ok and not is_main_win:
                    sent_ok = self._send_via_fallback(hwnd, message_text)

                if sent_ok:
                    logger.info(f"[SUCCESS] ส่งข้อความเข้าห้อง '{target_name}' สำเร็จในรอบที่ {attempt}!")

                    # ถ้าเปิดผ่านหน้าต่างหลัก ให้ล้างช่องค้นหาเพื่อความเป็นระเบียบ
                    if is_main_win:
                        try:
                            d = Desktop(backend='uia')
                            main_w = d.window(handle=hwnd)
                            search_box = main_w.child_window(class_name='LcTextField', control_type='Edit')
                            search_box.wrapper_object().set_edit_text('')
                        except Exception:
                            pass

                    return SendResult(
                        success=True,
                        chat_title=target_name,
                        message_preview=preview,
                        attempts=attempt,
                        timestamp=datetime.now()
                    )
                else:
                    last_error = "การส่งข้อความไม่สำเร็จ (ข้อความยังค้างอยู่ในช่องพิมพ์)"
                    logger.warning(f"รอบที่ {attempt} ไม่สำเร็จ: {last_error}")

            except Exception as e_proc:
                last_error = f"ข้อผิดพลาดระหว่างส่ง: {e_proc}"
                logger.error(f"รอบที่ {attempt} เกิด Exception: {e_proc}")

            if attempt < retry_count:
                logger.info(f"รอ {retry_delay} วินาทีก่อนลองใหม่...")
                time.sleep(retry_delay)

        # หากลองครบทุกรอบแล้วยังล้มเหลว
        logger.error(f"[FAILURE] ส่งข้อความเข้าห้อง '{chat_title}' ล้มเหลวหลังจากลอง {retry_count} ครั้ง: {last_error}")
        shot_path = capture_screenshot(prefix=f"fail_{chat_title}")

        return SendResult(
            success=False,
            chat_title=chat_title,
            message_preview=preview,
            attempts=retry_count,
            timestamp=datetime.now(),
            error_message=last_error,
            screenshot_path=shot_path
        )

