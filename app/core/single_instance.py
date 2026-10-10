"""
Single Instance Application Mutex for LINE Scheduler
Ensures only one instance of the application runs at any time.
"""

import sys
import ctypes
from ctypes import wintypes
import win32gui
import win32con

from app.core.logger import logger
from app.config import APP_NAME

# Global reference to prevent mutex from being garbage collected
_MUTEX_HANDLE = None
ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\LineScheduler_SingleInstance_Mutex"


def ensure_single_instance() -> bool:
    """
    ตรวจสอบว่ามี LINE Scheduler ทำงานอยู่แล้วหรือไม่
    หากมีอยู่แล้ว จะพยายามดึงหน้าต่างเดิมขึ้นมาและคืนค่า False
    หากเป็น Instance แรก จะคืนค่า True
    """
    global _MUTEX_HANDLE

    kernel32 = ctypes.windll.kernel32
    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    CreateMutexW.restype = wintypes.HANDLE

    _MUTEX_HANDLE = CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("[WARNING] ตรวจพบว่าโปรแกรม LINE Scheduler เปิดทำงานอยู่แล้ว (Instance ซ้ำ)")
        _restore_existing_window()
        return False

    logger.info("[INFO] Single-instance mutex acquired สำเร็จ")
    return True


def _restore_existing_window():
    """พยายามค้นหาหน้าต่างที่มีอยู่และดึงขึ้นมาด้านหน้า"""
    found_hwnds = []

    def enum_cb(hwnd, _):
        if win32gui.IsWindow(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.startswith(APP_NAME):
                found_hwnds.append(hwnd)
        return True

    try:
        win32gui.EnumWindows(enum_cb, None)
        for hwnd in found_hwnds:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
            break
    except Exception as e:
        logger.debug(f"ไม่สามารถดึงหน้าต่างเดิมขึ้นมาได้: {e}")

