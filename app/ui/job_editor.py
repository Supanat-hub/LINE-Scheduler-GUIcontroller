"""
Job Editor Modal Dialog for Adding and Editing Scheduled Tasks (No emojis used in GUI)
"""

import customtkinter as ctk
from datetime import datetime, date
from typing import Optional, Dict, Any, Callable

from app.core.preflight import get_all_line_windows, wake_line_from_tray


class JobEditorDialog(ctk.CTkToplevel):
    """หน้าต่างสำหรับเพิ่มหรือแก้ไขงานตั้งเวลาส่งข้อความ"""

    def __init__(
        self,
        parent,
        job_data: Optional[Dict[str, Any]] = None,
        on_save_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        super().__init__(parent)
        self.job_data = job_data or {}
        self.on_save_callback = on_save_callback
        self.is_edit_mode = bool(self.job_data.get("id"))

        # ตั้งค่าหน้าต่าง
        title_text = "แก้ไขงานตั้งเวลา" if self.is_edit_mode else "เพิ่มงานตั้งเวลาใหม่"
        self.title(title_text)
        self.geometry("640x720")
        self.minsize(580, 650)

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._populate_fields()

    def _create_widgets(self):
        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))

        title_label = ctk.CTkLabel(
            header_frame,
            text="แก้ไขงานตั้งเวลา" if self.is_edit_mode else "เพิ่มงานตั้งเวลาใหม่",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(side="left")

        # Scrollable Form Content
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # 1. ชื่องาน
        lbl_name = ctk.CTkLabel(scroll_frame, text="ชื่องาน (สำหรับจำ):", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_name.pack(fill="x", pady=(5, 2))
        self.entry_name = ctk.CTkEntry(scroll_frame, placeholder_text="เช่น แจ้งเตือนประชุมประจำวัน, รายงานยอดขาย")
        self.entry_name.pack(fill="x", pady=(0, 10))

        # 2. ห้องแชทเป้าหมาย
        lbl_chat = ctk.CTkLabel(scroll_frame, text="ห้องแชทเป้าหมาย (ชื่อเพื่อน/กลุ่ม หรือชื่อหน้าต่างแชท):", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_chat.pack(fill="x", pady=(5, 2))

        chat_input_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        chat_input_frame.pack(fill="x", pady=(0, 10))

        self.combo_chat = ctk.CTkComboBox(chat_input_frame, values=self._get_open_chat_titles())
        self.combo_chat.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_refresh_chats = ctk.CTkButton(
            chat_input_frame,
            text="ค้นหาหน้าต่าง",
            width=110,
            command=self._refresh_chat_titles
        )
        btn_refresh_chats.pack(side="right")

        # 3. รูปแบบการตั้งเวลา
        lbl_type = ctk.CTkLabel(scroll_frame, text="ความถี่การส่ง:", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_type.pack(fill="x", pady=(5, 2))

        self.seg_type = ctk.CTkSegmentedButton(
            scroll_frame,
            values=["ทุกวัน (Daily)", "วันในสัปดาห์ (Weekly)", "ครั้งเดียว (Once)", "ช่วงเวลา (Interval)"],
            command=self._on_schedule_type_changed
        )
        self.seg_type.pack(fill="x", pady=(0, 10))
        self.seg_type.set("ทุกวัน (Daily)")

        # 3.1 ตัวเลือกวันสำหรับ Weekly
        self.weekly_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        lbl_weekdays = ctk.CTkLabel(self.weekly_frame, text="เลือกวันที่ต้องการส่ง:", anchor="w")
        lbl_weekdays.pack(fill="x", pady=(2, 4))

        days_box = ctk.CTkFrame(self.weekly_frame)
        days_box.pack(fill="x")

        self.day_vars = {}
        day_keys = [("mon", "จันทร์"), ("tue", "อังคาร"), ("wed", "พุธ"), ("thu", "พฤหัส"), ("fri", "ศุกร์"), ("sat", "เสาร์"), ("sun", "อาทิตย์")]
        for code, label in day_keys:
            var = ctk.BooleanVar(value=(code not in ["sat", "sun"]))
            chk = ctk.CTkCheckBox(days_box, text=label, variable=var, width=70)
            chk.pack(side="left", padx=5, pady=6)
            self.day_vars[code] = var

        # 3.2 ตัวเลือกวันที่สำหรับ Once
        self.once_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        lbl_date = ctk.CTkLabel(self.once_frame, text="วันที่ระบุ (YYYY-MM-DD):", anchor="w")
        lbl_date.pack(fill="x", pady=(2, 4))
        self.entry_once_date = ctk.CTkEntry(self.once_frame, placeholder_text="YYYY-MM-DD")
        self.entry_once_date.pack(fill="x")

        # 3.3 ตัวเลือกนาทีสำหรับ Interval
        self.interval_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        lbl_interval = ctk.CTkLabel(self.interval_frame, text="ส่งซ้ำทุกๆ (นาที):", anchor="w")
        lbl_interval.pack(fill="x", pady=(2, 4))
        self.entry_interval = ctk.CTkEntry(self.interval_frame, placeholder_text="60")
        self.entry_interval.pack(fill="x")

        # 3.4 ตัวเลือกเวลา (ชั่วโมง : นาที)
        self.time_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        self.time_frame.pack(fill="x", pady=(5, 10))

        lbl_time = ctk.CTkLabel(self.time_frame, text="เวลาที่ส่ง (ชั่วโมง : นาที 24 ชม.):", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_time.pack(fill="x", pady=(0, 4))

        time_inputs = ctk.CTkFrame(self.time_frame, fg_color="transparent")
        time_inputs.pack(fill="x")

        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(60)]

        self.combo_hour = ctk.CTkComboBox(time_inputs, values=hours, width=90)
        self.combo_hour.set("09")
        self.combo_hour.pack(side="left")

        ctk.CTkLabel(time_inputs, text=" : ", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=5)

        self.combo_minute = ctk.CTkComboBox(time_inputs, values=minutes, width=90)
        self.combo_minute.set("00")
        self.combo_minute.pack(side="left")

        # 4. ข้อความที่จะส่ง
        lbl_msg = ctk.CTkLabel(scroll_frame, text="ข้อความที่ต้องการส่ง (รองรับหลายบรรทัด):", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_msg.pack(fill="x", pady=(10, 2))

        # แทรกตัวแปร
        vars_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        vars_frame.pack(fill="x", pady=(0, 4))

        btn_vars = [
            ("+ วันที่", "{วันที่}"),
            ("+ วัน", "{วัน}"),
            ("+ เวลา", "{เวลา}"),
            ("+ เดือน", "{เดือน}"),
            ("+ ปี", "{ปี}")
        ]
        for btn_text, var_code in btn_vars:
            b = ctk.CTkButton(
                vars_frame,
                text=btn_text,
                width=65,
                height=24,
                fg_color="#374151",
                hover_color="#4B5563",
                command=lambda v=var_code: self._insert_variable(v)
            )
            b.pack(side="left", padx=(0, 5))

        self.txt_message = ctk.CTkTextbox(scroll_frame, height=140)
        self.txt_message.pack(fill="x", pady=(0, 10))

        # 5. นโยบายเมื่อพลาดเวลา
        lbl_misfire = ctk.CTkLabel(scroll_frame, text="นโยบายกรณีเครื่องหลับ/พลาดเวลาส่ง:", anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl_misfire.pack(fill="x", pady=(5, 2))

        misfire_opts_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        misfire_opts_frame.pack(fill="x", pady=(0, 15))

        self.combo_misfire = ctk.CTkComboBox(
            misfire_opts_frame,
            values=["ส่งย้อนหลัง (ถ้าช้าไม่เกินเวลาที่กำหนด)", "ข้ามครั้งนี้ไปเลย"],
            width=280
        )
        self.combo_misfire.pack(side="left", padx=(0, 10))

        self.entry_grace = ctk.CTkEntry(misfire_opts_frame, width=90, placeholder_text="15")
        self.entry_grace.insert(0, "15")
        self.entry_grace.pack(side="left")
        ctk.CTkLabel(misfire_opts_frame, text="นาที").pack(side="left", padx=(5, 0))

        # Footer Actions
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=15)

        btn_cancel = ctk.CTkButton(footer, text="ยกเลิก", fg_color="#4B5563", hover_color="#6B7280", width=100, command=self.destroy)
        btn_cancel.pack(side="right", padx=(10, 0))

        btn_save = ctk.CTkButton(footer, text="บันทึกข้อมูล", width=130, command=self._on_save)
        btn_save.pack(side="right")

    def _get_open_chat_titles(self):
        """ค้นหาชื่อหน้าต่างแชทเดี่ยวของ LINE ที่เปิดอยู่ขณะนี้"""
        wins = get_all_line_windows()
        chats = [w['title'] for w in wins if not w['is_main']]
        return chats if chats else ["(ไม่พบหน้าต่างแยก - สามารถพิมพ์ชื่อห้องได้โดยตรง)"]

    def _refresh_chat_titles(self):
        titles = self._get_open_chat_titles()
        if not titles or titles[0].startswith("("):
            wake_line_from_tray()
            titles = self._get_open_chat_titles()
        self.combo_chat.configure(values=titles)
        if titles and not titles[0].startswith("("):
            self.combo_chat.set(titles[0])

    def _insert_variable(self, var_code: str):
        self.txt_message.insert("insert", var_code)

    def _on_schedule_type_changed(self, value: str):
        # ซ่อน frames ย่อยทั้งหมดก่อน
        self.weekly_frame.pack_forget()
        self.once_frame.pack_forget()
        self.interval_frame.pack_forget()

        if "Weekly" in value:
            self.weekly_frame.pack(fill="x", pady=(0, 10), before=self.time_frame)
            self.time_frame.pack(fill="x", pady=(5, 10))
        elif "Once" in value:
            self.once_frame.pack(fill="x", pady=(0, 10), before=self.time_frame)
            self.time_frame.pack(fill="x", pady=(5, 10))
        elif "Interval" in value:
            self.interval_frame.pack(fill="x", pady=(0, 10), before=self.time_frame)
            self.time_frame.pack_forget()  # Interval ไม่ใช้เวลาตายตัว
        else:
            self.time_frame.pack(fill="x", pady=(5, 10))

    def _populate_fields(self):
        if not self.job_data:
            self.entry_once_date.insert(0, date.today().isoformat())
            return

        self.entry_name.insert(0, self.job_data.get("name", ""))
        self.combo_chat.set(self.job_data.get("chat_title", ""))
        self.txt_message.insert("1.0", self.job_data.get("message_template", ""))

        stype = self.job_data.get("schedule_type", "daily")
        stime = self.job_data.get("schedule_time", "09:00")

        if stype == "once":
            self.seg_type.set("ครั้งเดียว (Once)")
            if " " in stime:
                dt_part, tm_part = stime.split(" ", 1)
                self.entry_once_date.insert(0, dt_part)
                if ":" in tm_part:
                    h, m = tm_part.split(":")[:2]
                    self.combo_hour.set(h)
                    self.combo_minute.set(m)
        elif stype == "weekly":
            self.seg_type.set("วันในสัปดาห์ (Weekly)")
            if ":" in stime:
                h, m = stime.split(":")[:2]
                self.combo_hour.set(h)
                self.combo_minute.set(m)
            saved_days = (self.job_data.get("days_of_week") or "").split(",")
            for code, var in self.day_vars.items():
                var.set(code in saved_days)
        elif stype == "interval":
            self.seg_type.set("ช่วงเวลา (Interval)")
            self.entry_interval.insert(0, str(self.job_data.get("interval_minutes", 60)))
        else:
            self.seg_type.set("ทุกวัน (Daily)")
            if ":" in stime:
                h, m = stime.split(":")[:2]
                self.combo_hour.set(h)
                self.combo_minute.set(m)

        self._on_schedule_type_changed(self.seg_type.get())

        misfire = self.job_data.get("misfire_policy", "grace_period")
        self.combo_misfire.set("ส่งย้อนหลัง (ถ้าช้าไม่เกินเวลาที่กำหนด)" if misfire == "grace_period" else "ข้ามครั้งนี้ไปเลย")
        self.entry_grace.delete(0, "end")
        self.entry_grace.insert(0, str(self.job_data.get("misfire_grace_minutes", 15)))

    def _on_save(self):
        name = self.entry_name.get().strip() or "งานไม่มีชื่อ"
        chat_title = self.combo_chat.get().strip()
        if chat_title.startswith("(") and chat_title.endswith(")"):
            chat_title = ""

        if not chat_title:
            return  # ผู้ใช้ยังไม่ได้กรอกชื่อห้อง

        message = self.txt_message.get("1.0", "end-1c").strip()
        if not message:
            return

        seg_val = self.seg_type.get()
        h = self.combo_hour.get()
        m = self.combo_minute.get()

        if "Once" in seg_val:
            schedule_type = "once"
            d = self.entry_once_date.get().strip() or date.today().isoformat()
            schedule_time = f"{d} {h}:{m}:00"
            days_of_week = None
            interval_minutes = None
        elif "Weekly" in seg_val:
            schedule_type = "weekly"
            schedule_time = f"{h}:{m}"
            active_days = [c for c, v in self.day_vars.items() if v.get()]
            days_of_week = ",".join(active_days) if active_days else "mon,tue,wed,thu,fri"
            interval_minutes = None
        elif "Interval" in seg_val:
            schedule_type = "interval"
            schedule_time = "00:00"
            days_of_week = None
            try:
                interval_minutes = int(self.entry_interval.get().strip())
            except ValueError:
                interval_minutes = 60
        else:
            schedule_type = "daily"
            schedule_time = f"{h}:{m}"
            days_of_week = None
            interval_minutes = None

        misfire_policy = "grace_period" if "ส่งย้อนหลัง" in self.combo_misfire.get() else "skip"
        try:
            misfire_grace_mins = int(self.entry_grace.get().strip())
        except ValueError:
            misfire_grace_mins = 15

        payload = {
            "name": name,
            "chat_title": chat_title,
            "message_template": message,
            "schedule_type": schedule_type,
            "schedule_time": schedule_time,
            "days_of_week": days_of_week,
            "interval_minutes": interval_minutes,
            "misfire_policy": misfire_policy,
            "misfire_grace_minutes": misfire_grace_mins,
            "is_enabled": self.job_data.get("is_enabled", 1)
        }

        if self.is_edit_mode:
            payload["id"] = self.job_data["id"]

        if self.on_save_callback:
            self.on_save_callback(payload)

        self.destroy()

