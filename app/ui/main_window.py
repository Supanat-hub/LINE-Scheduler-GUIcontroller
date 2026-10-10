"""
Main Application Window using CustomTkinter (Strictly NO emojis used in GUI)
"""

import sys
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from app.config import APP_NAME, APP_VERSION, LOGS_DIR, SCREENSHOTS_DIR, DATA_DIR
from app.db import Database
from app.core.logger import logger
from app.core.sender import LineSender
from app.core.scheduler import SchedulerManager
from app.core.health import HealthMonitor, HealthStatus
from app.core.power import (
    enable_runtime_keep_awake,
    disable_runtime_keep_awake,
    apply_optimized_power_settings,
    restore_original_power_settings,
    set_startup_enabled,
    is_startup_enabled,
    POWER_BACKUP_FILE
)
from app.ui.job_editor import JobEditorDialog
from app.ui.wizard import FirstRunWizard
from app.ui.tray import TrayManager
from app.core.defender import add_defender_exclusion

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    """หน้าต่างหลักของโปรแกรม LINE Scheduler"""

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("980x680")
        self.minsize(850, 580)

        # Core Services
        self.db = Database()
        self.sender = LineSender()
        self.scheduler_mgr = SchedulerManager(db=self.db, sender=self.sender)
        self.health_monitor = HealthMonitor(db=self.db, interval_secs=30)
        self.tray_mgr = TrayManager(
            on_show_window=self._show_window_from_tray,
            on_exit=self._safe_exit
        )

        # เปิด Keep-Awake ชั้นที่ 1
        enable_runtime_keep_awake()

        # ตั้งค่าเปิดพร้อม Windows เป็นค่าเริ่มต้น (Auto-start by Default)
        if self.db.get_setting("startup_initialized") is None:
            set_startup_enabled(True)
            self.db.set_setting("startup_initialized", "true")

        # สร้างหน้าต่าง UI
        self._create_layout()

        # เริ่มต้น Services
        self.scheduler_mgr.register_on_executed_callback(self._on_job_executed_callback)
        self.scheduler_mgr.start()

        self.health_monitor.register_callback(self._on_health_status_callback)
        self.health_monitor.start()

        self.tray_mgr.start()

        # จัดการการปิดหน้าต่าง (ย่อลงถาดระบบแทนการปิดจริง)
        self.protocol("WM_DELETE_WINDOW", self._on_close_button_clicked)

        # โหลดข้อมูลเริ่มต้น
        self.refresh_jobs_list()
        self.refresh_logs_list()
        self._check_health_once()

    def _create_layout(self):
        # 1. Header Bar
        header = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=0, height=65)
        header.pack(fill="x", side="top")

        # Title & Version
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=12)

        lbl_title = ctk.CTkLabel(title_box, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold"))
        lbl_title.pack(side="left")

        lbl_ver = ctk.CTkLabel(title_box, text=f"v{APP_VERSION}", font=ctk.CTkFont(size=12), text_color="#9CA3AF")
        lbl_ver.pack(side="left", padx=(8, 0), pady=(4, 0))

        # Status Indicator Badge
        self.status_badge = ctk.CTkLabel(
            title_box,
            text="[สถานะ: ปกติ]",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#10B981"
        )
        self.status_badge.pack(side="left", padx=(15, 0), pady=(2, 0))

        # Header Right Actions
        actions_box = ctk.CTkFrame(header, fg_color="transparent")
        actions_box.pack(side="right", padx=20, pady=12)

        btn_wizard = ctk.CTkButton(
            actions_box,
            text="วิซาร์ดเริ่มต้น",
            width=110,
            height=32,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._open_wizard
        )
        btn_wizard.pack(side="left", padx=(0, 10))

        btn_hide = ctk.CTkButton(
            actions_box,
            text="ย่อลงถาดระบบ",
            width=110,
            height=32,
            fg_color="#4B5563",
            hover_color="#6B7280",
            command=self._hide_to_tray
        )
        btn_hide.pack(side="left")

        # 2. Main Tab View
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_jobs = self.tabview.add("ตารางส่งข้อความ")
        self.tab_logs = self.tabview.add("ประวัติการส่ง")
        self.tab_settings = self.tabview.add("ตั้งค่าระบบ")

        self._build_jobs_tab()
        self._build_logs_tab()
        self._build_settings_tab()

    # ==========================================
    # Tab 1: ตารางงาน (Scheduled Jobs)
    # ==========================================

    def _build_jobs_tab(self):
        # Action Toolbar
        toolbar = ctk.CTkFrame(self.tab_jobs, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(5, 10))

        btn_add = ctk.CTkButton(
            toolbar,
            text="+ เพิ่มงานตั้งเวลาใหม่",
            font=ctk.CTkFont(weight="bold"),
            command=self._open_add_job_dialog
        )
        btn_add.pack(side="left", padx=(0, 10))

        btn_refresh = ctk.CTkButton(
            toolbar,
            text="รีเฟรชรายการ",
            width=110,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self.refresh_jobs_list
        )
        btn_refresh.pack(side="left", padx=(0, 10))

        btn_import = ctk.CTkButton(
            toolbar,
            text="นำเข้า JSON",
            width=100,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._import_jobs
        )
        btn_import.pack(side="right", padx=(5, 0))

        btn_export = ctk.CTkButton(
            toolbar,
            text="ส่งออก JSON",
            width=100,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._export_jobs
        )
        btn_export.pack(side="right")

        # Scrollable Container for Job Cards
        self.jobs_container = ctk.CTkScrollableFrame(self.tab_jobs)
        self.jobs_container.pack(fill="both", expand=True, padx=10, pady=5)

    def refresh_jobs_list(self):
        """โหลดและแสดงการ์ดงานทั้งหมดจากฐานข้อมูล"""
        for w in self.jobs_container.winfo_children():
            w.destroy()

        jobs = self.db.get_all_jobs()
        if not jobs:
            empty_lbl = ctk.CTkLabel(
                self.jobs_container,
                text="ยังไม่มีงานตั้งเวลาในระบบ\nกดปุ่ม '+ เพิ่มงานตั้งเวลาใหม่' ด้านบนเพื่อเริ่มต้น",
                font=ctk.CTkFont(size=15),
                text_color="#9CA3AF"
            )
            empty_lbl.pack(pady=60)
            return

        for job in jobs:
            self._create_job_card(job)

    def _create_job_card(self, job: dict):
        card = ctk.CTkFrame(self.jobs_container, fg_color="#1E293B", corner_radius=8)
        card.pack(fill="x", pady=6, padx=5)

        # Left Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=12)

        # Line 1: Title & Group
        top_line = ctk.CTkFrame(info_frame, fg_color="transparent")
        top_line.pack(fill="x")

        lbl_name = ctk.CTkLabel(
            top_line,
            text=job["name"],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_name.pack(side="left")

        lbl_group = ctk.CTkLabel(
            top_line,
            text=f"-> ห้องแชท: [{job['chat_title']}]",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#60A5FA"
        )
        lbl_group.pack(side="left", padx=(10, 0))

        # Line 2: Schedule & Next Run
        mid_line = ctk.CTkFrame(info_frame, fg_color="transparent")
        mid_line.pack(fill="x", pady=(4, 0))

        stype_th = {
            "daily": f"ทุกวัน เวลา {job['schedule_time']}",
            "weekly": f"วันในสัปดาห์ ({job.get('days_of_week', '')}) เวลา {job['schedule_time']}",
            "once": f"ครั้งเดียว เมื่อ {job['schedule_time']}",
            "interval": f"ส่งทุก {job.get('interval_minutes', 60)} นาที"
        }.get(job["schedule_type"], job["schedule_time"])

        lbl_schedule = ctk.CTkLabel(
            mid_line,
            text=f"ความถี่: {stype_th}",
            font=ctk.CTkFont(size=12),
            text_color="#D1D5DB"
        )
        lbl_schedule.pack(side="left")

        next_time = self.scheduler_mgr.get_next_run_time(job["id"])
        next_str = next_time.strftime("%d/%m/%Y %H:%M:%S") if next_time else "(ปิดใช้งาน)"
        lbl_next = ctk.CTkLabel(
            mid_line,
            text=f"| รอบถัดไป: {next_str}",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF"
        )
        lbl_next.pack(side="left", padx=(10, 0))

        # Line 3: Message Preview
        msg_preview = job["message_template"].replace("\n", " ")
        if len(msg_preview) > 60:
            msg_preview = msg_preview[:60] + "..."
        lbl_msg = ctk.CTkLabel(
            info_frame,
            text=f"ข้อความ: \"{msg_preview}\"",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF"
        )
        lbl_msg.pack(anchor="w", pady=(3, 0))

        # Right Controls
        ctrl_frame = ctk.CTkFrame(card, fg_color="transparent")
        ctrl_frame.pack(side="right", padx=15, pady=12)

        # Toggle Switch
        switch_var = ctk.BooleanVar(value=bool(job["is_enabled"]))
        switch = ctk.CTkSwitch(
            ctrl_frame,
            text="เปิดใช้งาน" if job["is_enabled"] else "ปิดใช้งาน",
            variable=switch_var,
            command=lambda j=job, v=switch_var: self._toggle_job_state(j, v)
        )
        switch.pack(side="right", padx=(10, 0))

        # Button: Edit
        btn_edit = ctk.CTkButton(
            ctrl_frame,
            text="แก้ไข",
            width=65,
            height=28,
            fg_color="#374151",
            hover_color="#4B5563",
            command=lambda j=job: self._open_edit_job_dialog(j)
        )
        btn_edit.pack(side="right", padx=(5, 0))

        # Button: Run Now
        btn_run = ctk.CTkButton(
            ctrl_frame,
            text="ส่งเดี๋ยวนี้",
            width=75,
            height=28,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=lambda j=job: self._run_job_now(j)
        )
        btn_run.pack(side="right", padx=(5, 0))

        # Button: Delete
        btn_del = ctk.CTkButton(
            ctrl_frame,
            text="ลบ",
            width=50,
            height=28,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=lambda j=job: self._delete_job_confirm(j)
        )
        btn_del.pack(side="right", padx=(5, 0))

    def _open_add_job_dialog(self):
        JobEditorDialog(self, on_save_callback=self._on_job_saved)

    def _open_edit_job_dialog(self, job: dict):
        JobEditorDialog(self, job_data=job, on_save_callback=self._on_job_saved)

    def _on_job_saved(self, job_payload: dict):
        if "id" in job_payload:
            job_id = job_payload["id"]
            self.db.update_job(job_id, **job_payload)
            self.scheduler_mgr.add_or_update_job(job_id)
        else:
            new_id = self.db.create_job(**job_payload)
            self.scheduler_mgr.add_or_update_job(new_id)

        self.refresh_jobs_list()

    def _toggle_job_state(self, job: dict, switch_var: ctk.BooleanVar):
        new_state = switch_var.get()
        self.db.toggle_job(job["id"], new_state)
        self.scheduler_mgr.add_or_update_job(job["id"])
        self.refresh_jobs_list()

    def _delete_job_confirm(self, job: dict):
        self.db.delete_job(job["id"])
        self.scheduler_mgr.remove_job(job["id"])
        self.refresh_jobs_list()

    def _run_job_now(self, job: dict):
        threading.Thread(
            target=lambda: self.scheduler_mgr._execute_job(job["id"]),
            daemon=True
        ).start()

    def _import_jobs(self):
        file_path = ctk.filedialog.askopenfilename(
            title="เลือกไฟล์ JSON ที่ต้องการนำเข้า",
            filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
                count = self.db.import_jobs_json(content)
                self.scheduler_mgr.reload_all_jobs()
                self.refresh_jobs_list()
            except Exception as e:
                logger.error(f"นำเข้า JSON ล้มเหลว: {e}")

    def _export_jobs(self):
        file_path = ctk.filedialog.asksaveasfilename(
            title="บันทึกไฟล์ตารางงาน JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            try:
                json_data = self.db.export_jobs_json()
                Path(file_path).write_text(json_data, encoding="utf-8")
            except Exception as e:
                logger.error(f"ส่งออก JSON ล้มเหลว: {e}")

    # ==========================================
    # Tab 2: ประวัติการส่ง (Execution Logs)
    # ==========================================

    def _build_logs_tab(self):
        toolbar = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(5, 10))

        btn_refresh = ctk.CTkButton(
            toolbar,
            text="รีเฟรชประวัติ",
            width=110,
            command=self.refresh_logs_list
        )
        btn_refresh.pack(side="left", padx=(0, 10))

        btn_open_folder = ctk.CTkButton(
            toolbar,
            text="เปิดโฟลเดอร์ Screenshots",
            width=180,
            fg_color="#374151",
            hover_color="#4B5563",
            command=lambda: os.startfile(SCREENSHOTS_DIR)
        )
        btn_open_folder.pack(side="left", padx=(0, 10))

        btn_clear = ctk.CTkButton(
            toolbar,
            text="ล้างประวัติทั้งหมด",
            width=120,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=self._clear_all_logs
        )
        btn_clear.pack(side="right")

        self.logs_container = ctk.CTkScrollableFrame(self.tab_logs)
        self.logs_container.pack(fill="both", expand=True, padx=10, pady=5)

    def refresh_logs_list(self):
        for w in self.logs_container.winfo_children():
            w.destroy()

        logs = self.db.get_execution_logs(limit=100)
        if not logs:
            lbl_empty = ctk.CTkLabel(
                self.logs_container,
                text="ยังไม่มีประวัติการส่งข้อความ",
                font=ctk.CTkFont(size=14),
                text_color="#9CA3AF"
            )
            lbl_empty.pack(pady=50)
            return

        for entry in logs:
            row = ctk.CTkFrame(self.logs_container, fg_color="#1E293B", corner_radius=6)
            row.pack(fill="x", pady=4, padx=5)

            # Status Badge
            is_ok = (entry["status"] == "SUCCESS")
            status_text = "[สำเร็จ]" if is_ok else "[ล้มเหลว]"
            status_color = "#10B981" if is_ok else "#EF4444"

            lbl_st = ctk.CTkLabel(
                row,
                text=status_text,
                font=ctk.CTkFont(weight="bold"),
                text_color=status_color,
                width=80
            )
            lbl_st.pack(side="left", padx=(10, 5), pady=8)

            # Details
            details_box = ctk.CTkFrame(row, fg_color="transparent")
            details_box.pack(side="left", fill="both", expand=True, pady=8)

            time_str = entry["executed_at"].replace("T", " ")[:19]
            top_t = f"{time_str} | ห้องแชท: [{entry['chat_title']}]"
            if entry.get("job_name"):
                top_t += f" (งาน: {entry['job_name']})"

            ctk.CTkLabel(details_box, text=top_t, font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")

            msg_p = entry["message_sent"].replace("\n", " ")
            if len(msg_p) > 75:
                msg_p = msg_p[:75] + "..."
            ctk.CTkLabel(details_box, text=f"ข้อความ: \"{msg_p}\"", text_color="#D1D5DB", anchor="w").pack(fill="x")

            if entry.get("error_message"):
                ctk.CTkLabel(details_box, text=f"สาเหตุ: {entry['error_message']}", text_color="#FCA5A5", anchor="w").pack(fill="x")

            # Screenshot Button (if failed and shot exists)
            if entry.get("screenshot_path") and Path(entry["screenshot_path"]).exists():
                btn_view_shot = ctk.CTkButton(
                    row,
                    text="ดูภาพหน้าจอ",
                    width=95,
                    height=28,
                    fg_color="#374151",
                    hover_color="#4B5563",
                    command=lambda p=entry["screenshot_path"]: os.startfile(p)
                )
                btn_view_shot.pack(side="right", padx=10)

    def _clear_all_logs(self):
        self.db.clear_logs()
        self.refresh_logs_list()

    # ==========================================
    # Tab 3: การตั้งค่าระบบ (Settings)
    # ==========================================

    def _build_settings_tab(self):
        scroll_settings = ctk.CTkScrollableFrame(self.tab_settings)
        scroll_settings.pack(fill="both", expand=True, padx=10, pady=5)

        # หมวดที่ 1: การจัดการพลังงานและกันเครื่องหลับ (Layers 1-3)
        sec1 = ctk.CTkFrame(scroll_settings)
        sec1.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(sec1, text="1. ระบบป้องกันเครื่องหลับและพักหน้าจอ (Keep-Awake Layers)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        lbl_p_desc = ctk.CTkLabel(
            sec1,
            text="- ชั้นที่ 1 (Runtime): ทำงานอัตโนมัติตลอดเวลาที่โปรแกรมนี้เปิดอยู่ (ป้องกัน Sleep/จอดับ)\n- ชั้นที่ 2 (System Power): ปรับแต่ง Power Plan ของ Windows ปิด Standby/จอดับ/พับฝาโน้ตบุ๊ก 24 ชม.\n- ชั้นที่ 3 (Auto-start): เปิดโปรแกรมพร้อมเปิดเครื่อง Windows อัตโนมัติ",
            justify="left",
            text_color="#9CA3AF"
        )
        lbl_p_desc.pack(anchor="w", padx=15, pady=(0, 10))

        power_btn_frame = ctk.CTkFrame(sec1, fg_color="transparent")
        power_btn_frame.pack(anchor="w", padx=15, pady=(0, 15))

        btn_power_opt = ctk.CTkButton(
            power_btn_frame,
            text="ตั้งค่าเครื่องให้พร้อมทำงาน 24 ชม. (Layer 2)",
            command=self._apply_power_settings
        )
        btn_power_opt.pack(side="left", padx=(0, 10))

        btn_power_restore = ctk.CTkButton(
            power_btn_frame,
            text="คืนค่าพลังงานเดิมของระบบ",
            fg_color="#4B5563",
            hover_color="#6B7280",
            command=self._restore_power_settings
        )
        btn_power_restore.pack(side="left")

        # Startup Switch
        self.var_startup = ctk.BooleanVar(value=is_startup_enabled())
        chk_startup = ctk.CTkCheckBox(
            sec1,
            text="เปิดโปรแกรม LINE Scheduler อัตโนมัติเมื่อเปิดเครื่อง (At log on)",
            variable=self.var_startup,
            command=self._toggle_startup
        )
        chk_startup.pack(anchor="w", padx=15, pady=(0, 15))

        # หมวดที่ 2: นโยบายเมื่อพลาดเวลา
        sec2 = ctk.CTkFrame(scroll_settings)
        sec2.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(sec2, text="2. นโยบายเมื่อพลาดเวลา (Misfire Policies)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        lbl_m_desc = ctk.CTkLabel(
            sec2,
            text="หากเครื่องคอมพิวเตอร์เพิ่งเปิดขึ้นมาใหม่ หรือเพิ่งเชื่อมต่ออินเทอร์เน็ตหลังจากเวลาที่นัดหมายไว้",
            text_color="#9CA3AF"
        )
        lbl_m_desc.pack(anchor="w", padx=15, pady=(0, 10))

        misfire_frame = ctk.CTkFrame(sec2, fg_color="transparent")
        misfire_frame.pack(anchor="w", padx=15, pady=(0, 15))

        ctk.CTkLabel(misfire_frame, text="ส่งย้อนหลังได้ไม่เกิน:").pack(side="left", padx=(0, 8))
        self.entry_default_grace = ctk.CTkEntry(misfire_frame, width=70)
        self.entry_default_grace.insert(0, self.db.get_setting("default_grace_minutes", "15"))
        self.entry_default_grace.pack(side="left")
        ctk.CTkLabel(misfire_frame, text="นาที").pack(side="left", padx=(5, 15))

        btn_save_misfire = ctk.CTkButton(
            misfire_frame,
            text="บันทึกค่านโยบาย",
            width=120,
            command=self._save_misfire_setting
        )
        btn_save_misfire.pack(side="left")

        # หมวดที่ 3: โฟลเดอร์ข้อมูลและระบบ
        sec3 = ctk.CTkFrame(scroll_settings)
        sec3.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(sec3, text="3. ข้อมูลและการวินิจฉัย (Diagnostics)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        diag_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        diag_frame.pack(anchor="w", padx=15, pady=(0, 15))

        btn_open_data = ctk.CTkButton(
            diag_frame,
            text="เปิดโฟลเดอร์จัดเก็บข้อมูล (Data Folder)",
            command=lambda: os.startfile(DATA_DIR)
        )
        btn_open_data.pack(side="left", padx=(0, 10))

        btn_open_logs = ctk.CTkButton(
            diag_frame,
            text="เปิดโฟลเดอร์ไฟล์ Log",
            fg_color="#374151",
            hover_color="#4B5563",
            command=lambda: os.startfile(LOGS_DIR)
        )
        btn_open_logs.pack(side="left")

        # หมวดที่ 4: ความปลอดภัยและข้อยกเว้น Antivirus (Windows Defender Exclusion)
        sec4 = ctk.CTkFrame(scroll_settings)
        sec4.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(sec4, text="4. การป้องกันไฟล์ถูกลบโดย Antivirus (Windows Defender Exclusion)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(15, 5))

        lbl_def_desc = ctk.CTkLabel(
            sec4,
            text="ป้องกัน Windows Defender ตรวจจับไฟล์ผิดพลาด (False Positive) หรือลบไฟล์ .exe อัตโนมัติ\nกดปุ่มด้านล่างเพื่อเพิ่มโฟลเดอร์ติดตั้งของโปรแกรมเข้าสู่รายการยกเว้นการสแกน (ต้องอนุญาตสิทธิ์ Admin)",
            justify="left",
            text_color="#9CA3AF"
        )
        lbl_def_desc.pack(anchor="w", padx=15, pady=(0, 10))

        def_action_frame = ctk.CTkFrame(sec4, fg_color="transparent")
        def_action_frame.pack(anchor="w", padx=15, pady=(0, 15))

        btn_add_exclusion = ctk.CTkButton(
            def_action_frame,
            text="[+] เพิ่มข้อยกเว้นใน Windows Defender",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._apply_defender_exclusion
        )
        btn_add_exclusion.pack(side="left", padx=(0, 10))

        self.lbl_defender_feedback = ctk.CTkLabel(
            def_action_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#10B981"
        )
        self.lbl_defender_feedback.pack(side="left")

    def _apply_defender_exclusion(self):
        self.lbl_defender_feedback.configure(
            text="กำลังส่งคำขอสิทธิ์ UAC...",
            text_color="#3B82F6"
        )
        self.update()

        ok, msg = add_defender_exclusion()
        if ok:
            self.lbl_defender_feedback.configure(
                text="[สำเร็จ] เพิ่มข้อยกเว้นเรียบร้อย (กรุณากด 'Yes' ที่หน้าต่าง UAC)",
                text_color="#10B981"
            )
        else:
            self.lbl_defender_feedback.configure(
                text=f"[ไม่สำเร็จ] {msg}",
                text_color="#EF4444"
            )

    def _apply_power_settings(self):
        ok = apply_optimized_power_settings()
        self._check_health_once()

    def _restore_power_settings(self):
        restore_original_power_settings()
        self._check_health_once()

    def _toggle_startup(self):
        set_startup_enabled(self.var_startup.get())

    def _save_misfire_setting(self):
        val = self.entry_default_grace.get().strip() or "15"
        self.db.set_setting("default_grace_minutes", val)

    # ==========================================
    # Global Actions & Callbacks
    # ==========================================

    def _open_wizard(self):
        FirstRunWizard(self, on_finished_callback=self.refresh_jobs_list)

    def _on_job_executed_callback(self, job_id: int, result):
        # ถูกเรียกจาก Scheduler Thread เมื่อส่งเสร็จ
        try:
            if self.winfo_exists():
                self.after(0, self.refresh_jobs_list)
                self.after(0, self.refresh_logs_list)
        except Exception:
            pass

    def _on_health_status_callback(self, status: HealthStatus):
        try:
            if self.winfo_exists():
                self.after(0, lambda: self._update_health_ui(status))
        except Exception:
            pass

    def _check_health_once(self):
        status = self.health_monitor.check_now()
        self._update_health_ui(status)

    def _update_health_ui(self, status: HealthStatus):
        if status.is_healthy:
            if getattr(status, 'in_tray', False):
                self.status_badge.configure(text="[สถานะ: ปกติ (ในถาดระบบ)]", text_color="#10B981")
                self.tray_mgr.update_status("green", "LINE Scheduler - ระบบพร้อมทำงาน (LINE อยู่ในถาดระบบ)")
            else:
                self.status_badge.configure(text="[สถานะ: ปกติ]", text_color="#10B981")
                self.tray_mgr.update_status("green", "LINE Scheduler - ระบบพร้อมทำงาน")
        elif not status.session_unlocked:
            self.status_badge.configure(text="[สถานะ: หน้าจอล็อก]", text_color="#EF4444")
            self.tray_mgr.update_status("red", "LINE Scheduler - หน้าจอล็อกอยู่")
        elif not status.line_running:
            self.status_badge.configure(text="[สถานะ: ไม่พบ LINE]", text_color="#EF4444")
            self.tray_mgr.update_status("red", "LINE Scheduler - ไม่พบแอป LINE")
        else:
            self.status_badge.configure(text="[สถานะ: แจ้งเตือน]", text_color="#F59E0B")
            self.tray_mgr.update_status("yellow", "LINE Scheduler - มีการแจ้งเตือน")

    def _on_close_button_clicked(self):
        # ย่อลงถาดระบบแทนการปิดโปรแกรม
        self._hide_to_tray()

    def _hide_to_tray(self):
        self.withdraw()
        self.tray_mgr.notify("LINE Scheduler", "โปรแกรมยังคงทำงานอยู่เบื้องหลังในถาดระบบ")

    def _show_window_from_tray(self):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _safe_exit(self):
        disable_runtime_keep_awake()
        self.health_monitor.stop()
        self.scheduler_mgr.shutdown(wait=False)
        self.tray_mgr.stop()
        self.quit()
