"""
LINE Scheduler Application Package
"""

import ctypes
import win32service
import win32con

# Ensure early attachment to the default interactive desktop before any GUI/UIA hooks are loaded
try:
    _hdesk = win32service.OpenDesktop('Default', 0, False, win32con.GENERIC_ALL)
    if _hdesk:
        ctypes.windll.user32.SetThreadDesktop(int(_hdesk))
except Exception:
    pass

__version__ = "1.0.3"

