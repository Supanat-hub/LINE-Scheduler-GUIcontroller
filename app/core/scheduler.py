"""
APScheduler-based Task Scheduler Manager with Database Synchronization and Misfire Policies
"""

import time
from datetime import datetime, date
from typing import Optional, Dict, Any, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db import Database
from app.core.logger import logger
from app.core.sender import LineSender, SendResult
from app.core.template import render_message_template


class SchedulerManager:
    """ตัวจัดการการตั้งเวลาและสั่งรันงานส่งข้อความอัตโนมัติ"""

    def __init__(self, db: Optional[Database] = None, sender: Optional[LineSender] = None):
        self.db = db or Database()
        self.sender = sender or LineSender()
        self.scheduler = BackgroundScheduler(daemon=True)
        self._on_job_executed_callbacks = []

    def register_on_executed_callback(self, callback: Callable[[int, SendResult], None]) -> None:
        """ลงทะเบียนฟังก์ชันเรียกกลับเมื่อทำงานเสร็จ (สำหรับอัปเดต GUI หรือ System Tray)"""
        self._on_job_executed_callbacks.append(callback)

    def start(self) -> None:
        """เริ่มต้นทำงาน Scheduler และโหลดงานทั้งหมดที่เปิดใช้งานจากฐานข้อมูล"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler เริ่มทำงานแล้ว (BackgroundScheduler Running)")
            self.reload_all_jobs()

    def shutdown(self, wait: bool = False) -> None:
        """หยุดการทำงานของ Scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler หยุดการทำงานแล้ว")

    def reload_all_jobs(self) -> None:
        """ล้างงานเดิมใน Scheduler และโหลดงานใหม่ที่เปิดใช้งานทั้งหมดจากฐานข้อมูล"""
        self.scheduler.remove_all_jobs()
        active_jobs = self.db.get_all_jobs(only_enabled=True)
        logger.info(f"กำลังโหลดงานที่เปิดใช้งานจากฐานข้อมูล {len(active_jobs)} งาน...")

        for job in active_jobs:
            self._schedule_single_job(job)

    def _schedule_single_job(self, job: Dict[str, Any]) -> bool:
        """สร้าง Trigger และลงทะเบียนงานเดี่ยวเข้า APScheduler"""
        job_id = job["id"]
        job_ref_id = f"line_job_{job_id}"

        # นโยบายพลาดเวลา (Misfire Grace Time)
        misfire_policy = job.get("misfire_policy", "grace_period")
        grace_mins = job.get("misfire_grace_minutes", 15)
        # ถ้า skip ให้เวลาน้อยมาก (1 วินาที) ถ้า grace_period ให้ตามนาทีที่กำหนด
        grace_time_sec = 1 if misfire_policy == "skip" else (grace_mins * 60)

        stype = job["schedule_type"]
        stime = job["schedule_time"]

        trigger = None
        try:
            if stype == "once":
                # 'YYYY-MM-DD HH:MM:SS' หรือ 'HH:MM'
                if len(stime) <= 5:  # เช่น '15:30' ให้ใช้วันนี้
                    today_str = date.today().isoformat()
                    stime = f"{today_str} {stime}:00"
                run_date = datetime.fromisoformat(stime)
                if run_date > datetime.now():
                    trigger = DateTrigger(run_date=run_date)
                else:
                    logger.warning(f"งาน ID {job_id} ('{job['name']}') เป็นแบบครั้งเดียวแต่เวลาผ่านไปแล้ว: {stime}")
                    return False

            elif stype == "daily":
                # 'HH:MM'
                parts = stime.split(":")
                hour, minute = int(parts[0]), int(parts[1])
                trigger = CronTrigger(hour=hour, minute=minute)

            elif stype == "weekly":
                # 'HH:MM' พร้อม days_of_week เช่น 'mon,tue,wed'
                parts = stime.split(":")
                hour, minute = int(parts[0]), int(parts[1])
                days = job.get("days_of_week") or "mon,tue,wed,thu,fri"
                trigger = CronTrigger(day_of_week=days, hour=hour, minute=minute)

            elif stype == "interval":
                minutes = job.get("interval_minutes") or 60
                trigger = IntervalTrigger(minutes=minutes)

            else:
                logger.error(f"ไม่รู้จักประเภทการตั้งเวลา '{stype}' สำหรับงาน ID {job_id}")
                return False

        except Exception as e:
            logger.error(f"สร้าง Trigger สำหรับงาน ID {job_id} ล้มเหลว: {e}")
            return False

        if trigger:
            try:
                # ถ้ามีงานเดิม ให้ลบออกก่อน
                if self.scheduler.get_job(job_ref_id):
                    self.scheduler.remove_job(job_ref_id)

                self.scheduler.add_job(
                    func=self._execute_job,
                    trigger=trigger,
                    args=[job_id],
                    id=job_ref_id,
                    name=job["name"],
                    misfire_grace_time=grace_time_sec,
                    coalesce=True,
                    replace_existing=True
                )
                logger.info(f"ลงทะเบียนงาน ID {job_id} ('{job['name']}') สำเร็จ (Trigger: {trigger})")
                return True
            except Exception as e:
                logger.error(f"เพิ่มงาน ID {job_id} เข้า Scheduler ไม่สำเร็จ: {e}")
                return False

        return False

    def add_or_update_job(self, job_id: int) -> bool:
        """อัปเดตงานใน Scheduler เมื่อมีการเพิ่ม/แก้ไขจาก GUI"""
        job = self.db.get_job(job_id)
        if not job:
            return False

        job_ref_id = f"line_job_{job_id}"
        if not job.get("is_enabled"):
            if self.scheduler.get_job(job_ref_id):
                self.scheduler.remove_job(job_ref_id)
            return True

        return self._schedule_single_job(job)

    def remove_job(self, job_id: int) -> None:
        """ลบงานออกจาก Scheduler"""
        job_ref_id = f"line_job_{job_id}"
        if self.scheduler.get_job(job_ref_id):
            self.scheduler.remove_job(job_ref_id)

    def get_next_run_time(self, job_id: int) -> Optional[datetime]:
        """ตรวจสอบเวลารันครั้งถัดไปของงาน"""
        job_ref_id = f"line_job_{job_id}"
        sched_job = self.scheduler.get_job(job_ref_id)
        return sched_job.next_run_time if sched_job else None

    def _execute_job(self, job_id: int) -> None:
        """ฟังก์ชันหลักที่ถูกเรียกเมื่อถึงเวลาส่งข้อความตามตาราง"""
        job = self.db.get_job(job_id)
        if not job:
            logger.warning(f"ไม่พบงาน ID {job_id} ในฐานข้อมูล ข้ามการส่ง")
            return

        if not job.get("is_enabled"):
            logger.info(f"งาน ID {job_id} ('{job['name']}') ถูกปิดใช้งานอยู่ ข้ามการส่ง")
            return

        chat_title = job["chat_title"]
        raw_template = job["message_template"]

        # 1. แปลงตัวแปรในข้อความ (Template Variables)
        rendered_message = render_message_template(raw_template)

        logger.info(f"--- ถึงเวลาทำงาน ID {job_id}: '{job['name']}' -> '{chat_title}' ---")

        # 2. ส่งข้อความผ่าน LineSender
        send_result = self.sender.send_message(
            chat_title=chat_title,
            message_text=rendered_message
        )

        # 3. บันทึกผลลงในตาราง execution_logs
        shot_str = str(send_result.screenshot_path) if send_result.screenshot_path else None
        self.db.add_execution_log(
            job_id=job_id,
            chat_title=chat_title,
            message_sent=rendered_message,
            status="SUCCESS" if send_result.success else "FAILED",
            attempts=send_result.attempts,
            error_message=send_result.error_message,
            screenshot_path=shot_str
        )

        # 4. หากเป็นงานแบบส่งครั้งเดียว (once) ให้ปิดใช้งานอัตโนมัติ
        if job["schedule_type"] == "once":
            self.db.toggle_job(job_id, False)
            self.remove_job(job_id)
            logger.info(f"งานแบบครั้งเดียว ID {job_id} ส่งเสร็จแล้ว ปิดใช้งานอัตโนมัติ")

        # 5. แจ้งเตือน Callbacks
        for cb in self._on_job_executed_callbacks:
            try:
                cb(job_id, send_result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

