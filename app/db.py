"""
SQLite Database Layer for LINE Scheduler
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from contextlib import contextmanager
from app.config import DB_PATH
from app.core.logger import logger


class Database:
    """ตัวจัดการฐานข้อมูล SQLite สำหรับงานตั้งเวลา ประวัติ และการตั้งค่า"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """สร้าง Connection พร้อม Row Factory และปิด Connection เสมอเมื่อออกจาก context"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """สร้างตารางที่จำเป็นทั้งหมดหากยังไม่มี"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. ตารางตารางงาน (jobs)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                chat_title TEXT NOT NULL,
                message_template TEXT NOT NULL,
                schedule_type TEXT NOT NULL,       -- 'once', 'daily', 'weekly', 'interval'
                schedule_time TEXT NOT NULL,       -- 'HH:MM' หรือ 'YYYY-MM-DD HH:MM:SS'
                days_of_week TEXT,                 -- เช่น 'mon,tue,wed,thu,fri' สำหรับ weekly
                interval_minutes INTEGER,          -- สำหรับ interval
                misfire_policy TEXT DEFAULT 'grace_period', -- 'skip' หรือ 'grace_period'
                misfire_grace_minutes INTEGER DEFAULT 15,
                is_enabled INTEGER DEFAULT 1,      -- 1 = เปิด, 0 = ปิด
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # 2. ตารางประวัติการทำงาน (execution_logs)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                chat_title TEXT NOT NULL,
                message_sent TEXT NOT NULL,
                status TEXT NOT NULL,              -- 'SUCCESS', 'FAILED'
                attempts INTEGER DEFAULT 1,
                error_message TEXT,
                screenshot_path TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE SET NULL
            )
            """)

            # 3. ตารางการตั้งค่าแอปพลิเคชัน (settings)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # ตั้งค่าเริ่มต้นหากยังไม่มี
            default_settings = {
                "theme": "dark",
                "default_misfire_policy": "grace_period",
                "default_grace_minutes": "15",
                "countdown_warning_secs": "10",
                "auto_start_windows": "0",
                "notify_on_failure": "1"
            }
            now = datetime.now().isoformat()
            for key, val in default_settings.items():
                cursor.execute("""
                INSERT OR IGNORE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """, (key, val, now))

            conn.commit()

    # ==========================
    # Job CRUD Operations
    # ==========================

    def create_job(
        self,
        name: str,
        chat_title: str,
        message_template: str,
        schedule_type: str,
        schedule_time: str,
        days_of_week: Optional[str] = None,
        interval_minutes: Optional[int] = None,
        misfire_policy: str = "grace_period",
        misfire_grace_minutes: int = 15,
        is_enabled: bool = True
    ) -> int:
        """สร้างงานตั้งเวลาใหม่"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO jobs (
                name, chat_title, message_template, schedule_type,
                schedule_time, days_of_week, interval_minutes,
                misfire_policy, misfire_grace_minutes, is_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, chat_title, message_template, schedule_type,
                schedule_time, days_of_week, interval_minutes,
                misfire_policy, misfire_grace_minutes, 1 if is_enabled else 0,
                now, now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลงานตาม ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_jobs(self, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """ดึงรายการงานทั้งหมด"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if only_enabled:
                cursor.execute("SELECT * FROM jobs WHERE is_enabled = 1 ORDER BY id DESC")
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def update_job(self, job_id: int, **kwargs) -> bool:
        """อัปเดตข้อมูลงานตามฟิลด์ที่ส่งเข้ามา"""
        if not kwargs:
            return False
        kwargs['updated_at'] = datetime.now().isoformat()
        fields = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values()) + [job_id]

        query = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def toggle_job(self, job_id: int, is_enabled: bool) -> bool:
        """เปิดหรือปิดการทำงานของงาน"""
        return self.update_job(job_id, is_enabled=1 if is_enabled else 0)

    def delete_job(self, job_id: int) -> bool:
        """ลบงานออกจากฐานข้อมูล"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==========================
    # Execution Log Operations
    # ==========================

    def add_execution_log(
        self,
        chat_title: str,
        message_sent: str,
        status: str,
        job_id: Optional[int] = None,
        attempts: int = 1,
        error_message: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> int:
        """บันทึกประวัติการส่งข้อความ"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO execution_logs (
                job_id, chat_title, message_sent, status,
                attempts, error_message, screenshot_path, executed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, chat_title, message_sent, status,
                attempts, error_message, screenshot_path, now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_execution_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """ดึงรายการประวัติการส่งล่าสุด"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT l.*, j.name as job_name
            FROM execution_logs l
            LEFT JOIN jobs j ON l.job_id = j.id
            ORDER BY l.id DESC
            LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def clear_logs(self) -> None:
        """ล้างประวัติการส่งทั้งหมด"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM execution_logs")
            conn.commit()

    # ==========================
    # Settings Operations
    # ==========================

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """อ่านค่าคอนฟิก"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """บันทึกหรืออัปเดตค่าคอนฟิก"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, str(value), now))
            conn.commit()

    # ==========================
    # Export / Import Operations
    # ==========================

    def export_jobs_json(self) -> str:
        """ส่งออกตารางงานทั้งหมดเป็น JSON สำหรับย้ายเครื่อง"""
        jobs = self.get_all_jobs()
        return json.dumps(jobs, ensure_ascii=False, indent=2)

    def import_jobs_json(self, json_str: str) -> int:
        """นำเข้าตารางงานจาก JSON"""
        data = json.loads(json_str)
        count = 0
        for item in data:
            self.create_job(
                name=item.get("name", "Imported Job"),
                chat_title=item["chat_title"],
                message_template=item["message_template"],
                schedule_type=item["schedule_type"],
                schedule_time=item["schedule_time"],
                days_of_week=item.get("days_of_week"),
                interval_minutes=item.get("interval_minutes"),
                misfire_policy=item.get("misfire_policy", "grace_period"),
                misfire_grace_minutes=item.get("misfire_grace_minutes", 15),
                is_enabled=bool(item.get("is_enabled", 1))
            )
            count += 1
        return count
