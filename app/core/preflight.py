"""
Pre-flight checks before attempting GUI automation
"""

import time
import ctypes
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import win32gui
import win32process
import win32service
import win32con

from app.core.logger import logger

_CACHED_HDESK = None


@dataclass
class PreflightReport:
    """ผลการตรวจสอบความพร้อมก่อนส่งข้อความ"""
    is_ready: bool
    line_running: bool
    session_unlocked: bool
    target_window_found: bool
    target_hwnd: Optional[int] = None
    target_title: Optional[str] = None
    main_window_hwnd: Optional[int] = None
    can_auto_open: bool = False
    open_chats: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def attach_to_default_desktop() -> bool:
    """สลับ Thread ปัจจุบันเข้าสู่ Default Interactive Desktop (ใช้ Cached hdesk)"""
    global _CACHED_HDESK
    try:
        if _CACHED_HDESK is None:
            _CACHED_HDESK = win32service.OpenDesktop('Default', 0, False, win32con.GENERIC_ALL)

        if _CACHED_HDESK:
            res = ctypes.windll.user32.SetThreadDesktop(int(_CACHED_HDESK))
            return res != 0
    except Exception:
        pass
    return False


def is_session_locked() -> bool:
    """ตรวจสอบว่าหน้าจอ Windows ถูกล็อก หรือมี ScreenSaver ทำงานอยู่หรือไม่"""
    attach_to_default_desktop()
    user32 = ctypes.windll.user32
    # OpenInputDesktop จะล้มเหลว (return NULL) หากเซสชันล็อกอยู่ (Winlogon desktop)
    DESKTOP_SWITCHDESKTOP = 0x0100
    hdesk = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not hdesk:
        return True
    user32.CloseDesktop(hdesk)
    return False


def get_all_line_windows() -> List[Dict]:
    """สแกนค้นหาหน้าต่างทั้งหมดของ LINE บนหน้าจอ (รวมถึงหน้าต่างที่ถูกย่อหรือซ่อนในถาดระบบ)"""
    attach_to_default_desktop()
    windows = []

    def enum_cb(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()
        cls = win32gui.GetClassName(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        is_visible = win32gui.IsWindowVisible(hwnd)
        is_iconic = win32gui.IsIconic(hwnd)

        # กรองเฉพาะหน้าต่างจริงของ LINE (ไม่รวม ToolTip, Observer, WebViewPool)
        if 'ScreenChange' in cls or 'ToolTip' in cls or 'MessageWindow' in cls or 'WebView' in cls:
            return

        is_line_class = ('Qt6' in cls and 'QWindowIcon' in cls) or ('LINE' in cls)

        if is_line_class and title:
            # รองรับทั้งกรณีหน้าต่างแสดงอยู่ ถูกย่อ (minimized) หรือซ่อนอยู่ในถาดระบบ (Tray)
            if is_visible or (title == 'LINE') or ('ChatWindow' in cls):
                windows.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': cls,
                    'rect': rect,
                    'is_main': (title == 'LINE'),
                    'is_minimized': bool(is_iconic),
                    'is_in_tray': not bool(is_visible)
                })

    for _ in range(3):
        try:
            windows.clear()
            win32gui.EnumWindows(enum_cb, None)
            break
        except Exception:
            time.sleep(0.1)

    return windows


def find_line_tray_window() -> Optional[int]:
    """ค้นหา HWND ของ QTrayIconMessageWindow ที่เป็นของ LINE Desktop"""
    attach_to_default_desktop()
    tray_hwnds = []

    def enum_cb(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return
        cls = win32gui.GetClassName(hwnd)
        if 'TrayIconMessageWindow' in cls:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                hproc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if hproc:
                    buf = ctypes.create_unicode_buffer(512)
                    size = ctypes.c_ulong(512)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
                        if 'line.exe' in buf.value.lower():
                            tray_hwnds.append(hwnd)
                    ctypes.windll.kernel32.CloseHandle(hproc)
            except Exception:
                tray_hwnds.append(hwnd)

    win32gui.EnumWindows(enum_cb, None)
    return tray_hwnds[0] if tray_hwnds else None


def wake_line_from_tray(timeout_sec: float = 3.0) -> bool:
    """
    ปลุกหน้าต่างหลักของ LINE ขึ้นมาจาก System Tray (Notification Area)
    โดยส่งสัญญาณ MYWM_NOTIFYICON (0x8065) เข้า QTrayIconMessageWindow
    """
    attach_to_default_desktop()
    tray_hwnd = find_line_tray_window()
    if not tray_hwnd:
        return False

    logger.info("พบ LINE ทำงานอยู่ในถาดระบบ (Tray) -> กำลังส่งสัญญาณปลุกหน้าต่างหลักขึ้นมา...")
    # MYWM_NOTIFYICON = 0x8065 (WM_APP + 101 ใน Qt 6)
    # Qt QSystemTrayIcon ใช้ ID = 1 หรือ 0
    for uId in [1, 0]:
        win32gui.PostMessage(tray_hwnd, 0x8065, uId, win32con.WM_LBUTTONDOWN)
        time.sleep(0.05)
        win32gui.PostMessage(tray_hwnd, 0x8065, uId, win32con.WM_LBUTTONUP)
        time.sleep(0.05)
        win32gui.PostMessage(tray_hwnd, 0x8065, uId, win32con.WM_LBUTTONDBLCLK)

    # รอจนกว่าหน้าต่างหลัก (Qt663QWindowIcon หรือ title='LINE') จะถูกสร้างขึ้นมา
    start_t = time.time()
    while time.time() - start_t < timeout_sec:
        time.sleep(0.3)
        windows = get_all_line_windows()
        if any(w['is_main'] for w in windows):
            logger.info("ปลุกหน้าต่างหลัก LINE จากถาดระบบสำเร็จเรียบร้อย")
            time.sleep(0.5)  # ให้เวลา UI ภายในของ LINE พร้อมรับคำสั่ง
            return True

    return False


def run_preflight_check(chat_title: str, auto_wake_tray: bool = True) -> PreflightReport:
    """ตรวจสอบความพร้อมทั้งหมดก่อนเริ่มกระบวนการส่งข้อความ"""
    errors = []
    attach_to_default_desktop()

    # 1. เช็กสถานะการล็อกหน้าจอ
    session_locked = is_session_locked()
    if session_locked:
        errors.append("หน้าจอ Windows ถูกล็อกอยู่ (Session Locked) ไม่สามารถส่ง GUI Automation ได้")

    # 2. เช็กหน้าต่าง LINE
    line_windows = get_all_line_windows()

    # หากไม่พบหน้าต่างใดๆ แต่ LINE ซ่อนอยู่ในถาดระบบ (Tray) ให้ทำการปลุกอัตโนมัติ
    if not line_windows and auto_wake_tray:
        tray_hwnd = find_line_tray_window()
        if tray_hwnd:
            logger.info("ไม่พบหน้าต่างบนหน้าจอ แต่ตรวจพบ LINE ซ่อนอยู่ในถาดระบบ (Tray) -> กำลังปลุกขึ้นมา...")
            if wake_line_from_tray():
                line_windows = get_all_line_windows()

    line_running = len(line_windows) > 0
    if not line_running:
        errors.append("ไม่พบหน้าต่าง LINE Desktop ที่เปิดอยู่ กรุณาเปิด LINE และเข้าสู่ระบบ")

    # 3. เช็กหน้าต่างแชทเป้าหมาย (แยกหน้าต่าง Pop-out)
    chat_windows = [w for w in line_windows if not w['is_main']]
    open_chat_titles = [w['title'] for w in chat_windows]

    target_window = None
    target_clean = chat_title.strip().lower()
    for w in chat_windows:
        w_title_clean = w['title'].strip().lower()
        if target_clean == w_title_clean or target_clean in w_title_clean:
            target_window = w
            break

    target_found = target_window is not None
    target_hwnd = target_window['hwnd'] if target_window else None
    resolved_title = target_window['title'] if target_window else None

    # ค้นหาหน้าต่างหลัก LINE
    main_window = next((w for w in line_windows if w['is_main']), None)
    main_hwnd = main_window['hwnd'] if main_window else None

    can_auto_open = False
    if target_found:
        can_auto_open = False
        is_ready = (not session_locked) and line_running
    elif main_window:
        # แม้ยังไม่ได้เปิดหน้าต่างแชทแยกไว้ แต่หน้าต่างหลักของ LINE เปิดอยู่ -> รองรับ Auto-Open!
        can_auto_open = True
        is_ready = (not session_locked) and line_running
    else:
        can_auto_open = False
        is_ready = False
        errors.append(f"ไม่พบหน้าต่างแชท '{chat_title}' และไม่พบหน้าต่างหลักของ LINE")

    return PreflightReport(
        is_ready=is_ready,
        line_running=line_running,
        session_unlocked=not session_locked,
        target_window_found=target_found,
        target_hwnd=target_hwnd,
        target_title=resolved_title,
        main_window_hwnd=main_hwnd,
        can_auto_open=can_auto_open,
        open_chats=open_chat_titles,
        errors=errors
    )
