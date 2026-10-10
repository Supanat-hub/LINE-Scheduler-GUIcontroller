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
from app.core.preflight import run_preflight_check, attach_to_default_desktop, get_all_line_windows


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

    @staticmethod
    def _verify_chat_window(hwnd: int, expected_title: str) -> bool:
        """ตรวจสอบว่า HWND มีอยู่จริง และ Window Title มีชื่อห้องแชทเป้าหมายอยู่หรือไม่"""
        if not win32gui.IsWindow(hwnd):
            return False
        title = win32gui.GetWindowText(hwnd).strip()
        if not title or title == 'LINE':
            return False
        exp = expected_title.strip().lower()
        actual = title.lower()
        return (exp == actual) or (exp in actual)

    @staticmethod
    def _close_window(hwnd: int) -> None:
        """ปิดหน้าต่างแชทอย่างปลอดภัยด้วย WM_CLOSE"""
        try:
            if win32gui.IsWindow(hwnd):
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(0.3)
        except Exception:
            pass

    @staticmethod
    def _reset_main_window_search(main_hwnd: int) -> None:
        """ล้างช่องค้นหาในหน้าต่างหลักและคืนสถานะด้วย ESC"""
        try:
            attach_to_default_desktop()
            # ส่ง ESC 2 ครั้งเพื่อเคลียร์การค้นหาและคืนหน้าจอหลัก
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            time.sleep(0.05)
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            time.sleep(0.1)
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            time.sleep(0.05)
            win32gui.PostMessage(main_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            time.sleep(0.2)
        except Exception:
            pass

    def _pop_out_embedded_chat(self, main_hwnd: int, expected_title: str, timeout_sec: float = 3.0) -> Optional[int]:
        """
        คลิกปุ่ม Pop-out บนแถบหัวเรื่องห้องแชทในหน้าต่างหลักเพื่อดีดห้องแชทออกเป็นหน้าต่างแยก
        และตรวจสอบ Window Title ของหน้าต่างใหม่ทันที
        """
        try:
            attach_to_default_desktop()
            d = Desktop(backend='uia')
            main_w = d.window(handle=main_hwnd)
            panels = [c for c in main_w.descendants() if c.class_name() == 'AllInOneChatPanel']
            if not panels:
                return None

            panel = panels[0]
            # ค้นหาปุ่มบน Header (แถบด้านบนของ AllInOneChatPanel)
            header_buttons = [
                c for c in panel.descendants()
                if 'Button' in c.class_name() and c.rectangle().top < panel.rectangle().top + 60
            ]
            if len(header_buttons) < 2:
                logger.warning("ไม่พบปุ่ม Pop-out บน Header ของ AllInOneChatPanel")
                return None

            # ปุ่ม Pop-out คือ Button ลำดับที่ 2 (index 1) ถัดจากปุ่มปิดเสียง
            pop_btn = header_buttons[1]
            r = pop_btn.rectangle()
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            logger.info(f"คลิกปุ่ม Pop-out ที่พิกัด ({cx}, {cy}) เพื่อแยกหน้าต่าง...")
            pyautogui.click(cx, cy)

            # รอจนกว่าหน้าต่างแชทแยกที่มีชื่อจะปรากฏขึ้นมา
            start_t = time.time()
            while time.time() - start_t < timeout_sec:
                time.sleep(0.3)
                windows = get_all_line_windows()
                for w in windows:
                    if not w['is_main'] and not w['is_in_tray']:
                        hwnd = w['hwnd']
                        if self._verify_chat_window(hwnd, expected_title):
                            logger.info(f"แยกหน้าต่างสำเร็จ: ตรวจพบหน้าต่าง '{w['title']}' (HWND: {hwnd}) ตรงกับเป้าหมาย 100%")
                            return hwnd
                        elif w['title']:
                            # ถ้าเด้งขึ้นมาแต่ชื่อไม่ตรง
                            logger.warning(f"[MISMATCH] หน้าต่างที่เด้งออกมาชื่อ '{w['title']}' ไม่ตรงกับเป้าหมาย '{expected_title}'")
                            self._close_window(hwnd)
                            return None

            return None
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการ Pop-out แชท: {e}")
            return None

    def _open_chat_in_main_window(self, main_hwnd: int, chat_title: str, attempt: int = 1) -> Optional[int]:
        """
        ค้นหาและเปิดห้องแชทผ่านหน้าต่างหลักด้วยกระบวนการตรวจสอบแบบ 3 ชั้น (Search Settle + Selection + Pop-out Verify)
        คืนค่า HWND ของหน้าต่างแชทที่ยืนยันแล้วว่าชื่อตรง 100% หรือคืนค่า None หากไม่ตรง/ไม่สำเร็จ
        """
        try:
            self.focus_window(main_hwnd)
            time.sleep(0.3)
            d = Desktop(backend='uia')
            main_w = d.window(handle=main_hwnd)

            # ค้นหาช่องค้นหา (LcTextField)
            search_box = main_w.child_window(class_name='LcTextField', control_type='Edit')
            elem = search_box.wrapper_object()

            # 1. ล้างช่องค้นหาให้สะอาด
            elem.set_edit_text('')
            time.sleep(0.3)

            # 2. พิมพ์ชื่อห้องแชทเป้าหมาย
            elem.set_edit_text(chat_title)

            # 3. ชั้นที่ 1: ตรวจสอบ Search Settling (รอจนรายการผลการค้นหาอัปเดต)
            max_wait = 2.0 + (attempt * 0.5)
            start_poll = time.time()
            settled_list = None

            while time.time() - start_poll < max_wait:
                time.sleep(0.2)
                # ค้นหารายการผลการค้นหา (LcListView ฝั่งซ้าย)
                lists = [
                    c for c in main_w.descendants()
                    if c.class_name() == 'LcListView' and c.rectangle().left < 400
                ]
                if lists:
                    children = lists[0].children()
                    # ถ้า children == 0 แปลว่าค้นหาเสร็จแล้วและไม่พบผลลัพธ์
                    if len(children) == 0:
                        logger.warning(f"ค้นหา '{chat_title}' แล้วไม่พบผลการค้นหา (ผลลัพธ์ = 0)")
                        self._reset_main_window_search(main_hwnd)
                        return None
                    # ถ้า children >= 2 (มี Section Header + Chat Item) แปลว่าผลการค้นหามาแล้ว
                    elif len(children) >= 2:
                        settled_list = lists[0]
                        break

            if not settled_list:
                logger.warning(f"รอผลการค้นหา '{chat_title}' เกินเวลา {max_wait:.1f} วินาที")
                self._reset_main_window_search(main_hwnd)
                return None

            # หน่วงเวลาสั้นๆ เพื่อให้ UI นิ่งสนิท
            time.sleep(0.3)

            # 4. ชั้นที่ 2: เลือกรายการผลลัพธ์แรก (Item index 1 ข้าม Header index 0)
            items = settled_list.children()
            if len(items) < 2:
                self._reset_main_window_search(main_hwnd)
                return None

            chat_item = items[1]
            r = chat_item.rectangle()
            click_x = (r.left + r.right) // 2
            click_y = (r.top + r.bottom) // 2
            logger.info(f"คลิกเลือกผลการค้นหาห้องแชทที่พิกัด ({click_x}, {click_y})...")
            pyautogui.click(click_x, click_y)
            time.sleep(0.6)

            # 5. ชั้นที่ 3: ตรวจสอบสถานะการเปิดห้องแชท
            # 5.1 ตรวจสอบว่าเปิดเป็นหน้าต่างแยกแล้วหรือไม่
            windows = get_all_line_windows()
            for w in windows:
                if not w['is_main'] and not w['is_in_tray']:
                    hwnd = w['hwnd']
                    if self._verify_chat_window(hwnd, chat_title):
                        logger.info(f"ตรวจพบหน้าต่างแชทแยก '{w['title']}' ตรงกับเป้าหมาย '{chat_title}' เรียบร้อย")
                        return hwnd
                    else:
                        logger.warning(f"[MISMATCH] หน้าต่างที่เปิดขึ้นมาชื่อ '{w['title']}' ไม่ตรงกับเป้าหมาย '{chat_title}'")
                        self._close_window(hwnd)
                        self._reset_main_window_search(main_hwnd)
                        return None

            # 5.2 หากเปิดค้างอยู่ในหน้าต่างหลัก (AllInOneChatPanel) ให้สั่ง Pop-out เพื่อดึงชื่อมาเช็ก
            pop_hwnd = self._pop_out_embedded_chat(main_hwnd, chat_title)
            if pop_hwnd and self._verify_chat_window(pop_hwnd, chat_title):
                return pop_hwnd

            logger.warning(f"ไม่สามารถยืนยันความถูกต้องของห้องแชท '{chat_title}' ได้")
            self._reset_main_window_search(main_hwnd)
            return None

        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการค้นหาและเปิดแชทผ่านหน้าต่างหลัก: {e}")
            self._reset_main_window_search(main_hwnd)
            return None

    def send_message(
        self,
        chat_title: str,
        message_text: str,
        retry_count: int = DEFAULT_RETRY_COUNT,
        retry_delay: float = DEFAULT_RETRY_DELAY_SEC
    ) -> SendResult:
        """
        ส่งข้อความไปยังห้องแชทที่ระบุ พร้อมระบบตรวจสอบชื่อ 3 ชั้น (Multi-layer Verification)
        และระบบทำซ้ำอัตโนมัติ (Auto-Retry with Circuit Breaker)
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
                    logger.info(f"รอ {min(retry_delay, 3.0)} วินาทีก่อนลองใหม่...")
                    time.sleep(min(retry_delay, 3.0))
                continue

            # กำหนดหน้าต่างเป้าหมายพร้อมระบบตรวจสอบความถูกต้อง (Target Verification)
            hwnd = None
            target_name = None

            # ตรวจสอบหน้าต่างแยกที่มีอยู่เดิม
            if report.target_window_found and report.target_hwnd:
                if self._verify_chat_window(report.target_hwnd, chat_title):
                    hwnd = report.target_hwnd
                    target_name = win32gui.GetWindowText(hwnd).strip()
                    logger.info(f"พบหน้าต่างแยก '{target_name}' (HWND: {hwnd}) ชื่อตรงกับเป้าหมายเรียบร้อย")
                else:
                    wrong_title = win32gui.GetWindowText(report.target_hwnd)
                    logger.warning(f"หน้าต่างแยก HWND: {report.target_hwnd} ชื่อ '{wrong_title}' ไม่ตรงกับเป้าหมาย '{chat_title}' -> ปิดทิ้ง")
                    self._close_window(report.target_hwnd)

            # หากยังไม่ได้หน้าต่างที่ยืนยันแล้ว ให้เริ่มกระบวนการค้นหาและเปิดผ่านหน้าต่างหลัก
            if not hwnd and report.main_window_hwnd:
                logger.info(f"เริ่มกระบวนการค้นหาและยืนยันห้องแชท '{chat_title}' ในหน้าต่างหลัก...")
                opened_hwnd = self._open_chat_in_main_window(report.main_window_hwnd, chat_title, attempt)
                if opened_hwnd and self._verify_chat_window(opened_hwnd, chat_title):
                    hwnd = opened_hwnd
                    target_name = win32gui.GetWindowText(hwnd).strip()
                else:
                    last_error = f"เปิดห้องแชทไม่ตรงกับเป้าหมาย '{chat_title}' หรือค้นหาไม่สำเร็จ"
                    logger.warning(f"[RETRY] รอบที่ {attempt}/{retry_count} ไม่ผ่าน: {last_error} -> เตรียมทำซ้ำในรอบถัดไป...")
                    if attempt < retry_count:
                        time.sleep(min(retry_delay, 3.0))
                    continue

            if not hwnd:
                last_error = f"ไม่สามารถระบุหน้าต่างห้องแชทที่ตรงกับเป้าหมาย '{chat_title}' ได้"
                logger.warning(f"รอบที่ {attempt} ไม่ผ่าน: {last_error}")
                if attempt < retry_count:
                    time.sleep(min(retry_delay, 3.0))
                continue

            # 2. ปราการด่านสุดท้ายก่อนพิมพ์และส่งเด็ดขาด (Fail-Safe Circuit Breaker)
            if not self._verify_chat_window(hwnd, chat_title):
                actual = win32gui.GetWindowText(hwnd).strip() if win32gui.IsWindow(hwnd) else "N/A"
                last_error = f"ตรวจพบชื่อหน้าต่าง '{actual}' ไม่ตรงกับ '{chat_title}'"
                logger.error(f"[SAFETY_ABORT] {last_error} ตัดวงจรทันทีเพื่อความปลอดภัยสูงสุด!")
                self._close_window(hwnd)
                if report.main_window_hwnd:
                    self._reset_main_window_search(report.main_window_hwnd)
                if attempt < retry_count:
                    time.sleep(min(retry_delay, 3.0))
                continue

            try:
                # 3. ดึงหน้าต่างขึ้นมา
                self.focus_window(hwnd)

                # 4. ส่งข้อความด้วย Engine 1 (Direct UIA)
                sent_ok = False
                try:
                    sent_ok = self._send_via_uia(hwnd, message_text)
                except Exception as e_uia:
                    logger.warning(f"Engine 1 (UIA) ล้มเหลว: {e_uia}")

                # 5. ถ้ายังไม่สำเร็จ ให้ลอง Fallback (คลิปบอร์ด)
                if not sent_ok:
                    sent_ok = self._send_via_fallback(hwnd, message_text)

                if sent_ok:
                    logger.info(f"[SUCCESS] ส่งข้อความเข้าห้อง '{target_name}' สำเร็จในรอบที่ {attempt}!")

                    # ล้างช่องค้นหาหน้าต่างหลักเพื่อความเป็นระเบียบ
                    if report.main_window_hwnd:
                        self._reset_main_window_search(report.main_window_hwnd)

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
                logger.info(f"รอ {min(retry_delay, 3.0)} วินาทีก่อนลองใหม่...")
                time.sleep(min(retry_delay, 3.0))

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

