"""
System Tray Integration using pystray with Status Icon and 10s Countdown Alerts (No emojis used in GUI)
"""

import threading
import time
from typing import Optional, Callable
import pystray
from PIL import Image

from app.ui.icons import create_status_icon
from app.core.logger import logger


class TrayManager:
    """ตัวจัดการไอคอนถาดระบบ (System Tray) พร้อมเมนูคลิกขวาและการแจ้งเตือน"""

    def __init__(
        self,
        on_show_window: Optional[Callable] = None,
        on_exit: Optional[Callable] = None
    ):
        self.on_show_window = on_show_window
        self.on_exit = on_exit

        self.current_status_color = "green"
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_menu(self):
        return pystray.Menu(
            pystray.MenuItem("เปิดหน้าต่างหลัก", self._action_show),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ออกจากโปรแกรม", self._action_exit)
        )

    def _action_show(self, icon, item):
        if self.on_show_window:
            self.on_show_window()

    def _action_exit(self, icon, item):
        self.stop()
        if self.on_exit:
            self.on_exit()

    def update_status(self, color: str = "green", tooltip: str = "LINE Scheduler"):
        """อัปเดตสีไอคอนในถาดระบบ: 'green' (ปกติ), 'yellow' (เตือน), 'red' (ข้อผิดพลาด)"""
        self.current_status_color = color
        if self._icon:
            self._icon.icon = create_status_icon(color)
            self._icon.title = tooltip

    def notify(self, title: str, message: str):
        """ส่งการแจ้งเตือน Balloon Notification ผ่านถาดระบบ Windows"""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.warning(f"ส่งการแจ้งเตือนถาดระบบไม่สำเร็จ: {e}")

    def start(self):
        """เริ่มต้นการทำงานของ System Tray ใน Background Thread"""
        if self._icon is None:
            self._icon = pystray.Icon(
                "LINE_Scheduler",
                create_status_icon(self.current_status_color),
                "LINE Scheduler - ทำงานเบื้องหลัง",
                menu=self._create_menu()
            )
            self._thread = threading.Thread(target=self._icon.run, daemon=True, name="SystemTrayThread")
            self._thread.start()
            logger.info("System Tray เริ่มทำงานแล้ว")

    def stop(self):
        """ปิดการทำงานของ System Tray"""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
            logger.info("System Tray หยุดการทำงานแล้ว")

