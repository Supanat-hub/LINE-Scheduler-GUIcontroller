"""
System & LINE Desktop Health Monitoring Module (1-Minute Periodic Checker)
"""

import threading
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Callable

from app.core.logger import logger
from app.core.preflight import (
    is_session_locked,
    get_all_line_windows,
    find_line_tray_window,
    attach_to_default_desktop
)
from app.db import Database


@dataclass
class HealthStatus:
    """ผลการตรวจสอบสุขภาพของระบบและแอป LINE"""
    is_healthy: bool
    line_running: bool
    session_unlocked: bool
    in_tray: bool = False
    open_chats: List[str] = field(default_factory=list)
    missing_chats: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)


class HealthMonitor:
    """ตัวเฝ้าระวังสุขภาพระบบแบบ Background Thread ทำงานทุก 1 นาที (หรือตามความถี่ที่กำหนด)"""

    def __init__(self, db: Optional[Database] = None, interval_secs: int = 60):
        self.db = db or Database()
        self.interval_secs = interval_secs
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_status_changed_callbacks: List[Callable[[HealthStatus], None]] = []
        self._last_status: Optional[HealthStatus] = None

    def register_callback(self, callback: Callable[[HealthStatus], None]) -> None:
        """ลงทะเบียนฟังก์ชันแจ้งเตือนเมื่อสถานะสุขภาพเปลี่ยนแปลง"""
        self._on_status_changed_callbacks.append(callback)

    def check_now(self) -> HealthStatus:
        """ทำการตรวจสุขภาพทันทีหนึ่งครั้ง"""
        attach_to_default_desktop()
        warnings = []

        # 1. เช็กการล็อกเซสชัน
        session_unlocked = not is_session_locked()
        if not session_unlocked:
            warnings.append("[!] หน้าจอ Windows ถูกล็อกอยู่ (Session Locked) ระบบจะไม่สามารถคลิก/ส่งข้อความได้")

        # 2. เช็กหน้าต่าง LINE (รวมถึงกรณีซ่อนในถาดระบบ Tray)
        windows = get_all_line_windows()
        line_running = len(windows) > 0
        in_tray = False

        if not line_running:
            tray_hwnd = find_line_tray_window()
            if tray_hwnd:
                line_running = True
                in_tray = True

        if not line_running:
            warnings.append("[!] ไม่พบหน้าต่าง LINE Desktop ทำงานอยู่")

        open_chats = [w['title'] for w in windows if not w['is_main']]
        has_main_win = any(w['is_main'] for w in windows)

        # 3. เช็กว่าห้องแชทของงานที่เปิดใช้งานอยู่เปิดครบไหม
        active_jobs = self.db.get_all_jobs(only_enabled=True)
        missing_chats = []
        for job in active_jobs:
            target = job['chat_title'].strip().lower()
            matched = any(target in c.strip().lower() for c in open_chats)
            if not matched and job['chat_title'] not in missing_chats:
                missing_chats.append(job['chat_title'])

        if missing_chats:
            if has_main_win:
                logger.debug(f"ห้องแชทที่ยังไม่ได้เปิดแท็บแยก (รองรับ Auto-Open ผ่านหน้าต่างหลัก): {', '.join(missing_chats)}")
            elif in_tray:
                logger.debug(f"LINE ทำงานอยู่ในถาดระบบ (รองรับ Auto-Wake และ Auto-Open ผ่านหน้าต่างหลัก): {', '.join(missing_chats)}")
            else:
                warnings.append(
                    f"[!] ไม่พบหน้าต่างแชทแยกและไม่พบหน้าต่างหลัก LINE: {', '.join(missing_chats)}"
                )

        is_healthy = session_unlocked and line_running and (len(missing_chats) == 0 or has_main_win or in_tray)

        status = HealthStatus(
            is_healthy=is_healthy,
            line_running=line_running,
            session_unlocked=session_unlocked,
            in_tray=in_tray,
            open_chats=open_chats,
            missing_chats=missing_chats,
            warnings=warnings,
            checked_at=datetime.now()
        )

        self._last_status = status
        return status

    def _monitor_loop(self) -> None:
        """ลูปเฝ้าระวังเบื้องหลัง"""
        logger.info(f"Health Monitor เริ่มทำงานแล้ว (ตรวจสอบทุก {self.interval_secs} วินาที)")
        while not self._stop_event.is_set():
            try:
                status = self.check_now()
                if not status.is_healthy:
                    logger.warning(f"Health Check พบปัญหา: {'; '.join(status.warnings)}")
                else:
                    logger.debug("Health Check ปกติ: LINE และเซสชันพร้อมทำงาน")

                # แจ้งเตือน Callback
                for cb in self._on_status_changed_callbacks:
                    try:
                        cb(status)
                    except Exception as e:
                        logger.error(f"Health Callback error: {e}")

            except Exception as e:
                logger.error(f"Health Monitor เกิดข้อผิดพลาด: {e}")

            # รอเวลาหรือหยุดเมื่อมีสัญญาณ
            self._stop_event.wait(self.interval_secs)

        logger.info("Health Monitor หยุดการทำงานแล้ว")

    def start(self) -> None:
        """เริ่มเฝ้าระวัง"""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="HealthMonitorThread")
            self._thread.start()

    def stop(self) -> None:
        """หยุดเฝ้าระวัง"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

