"""
First-Run Setup Wizard (4 Steps, No emojis used in GUI)
"""

import customtkinter as ctk
import time
from typing import Optional, Callable

from app.core.preflight import (
    get_all_line_windows,
    is_session_locked,
    find_line_tray_window,
    wake_line_from_tray
)
from app.core.power import apply_optimized_power_settings
from app.core.sender import LineSender


class FirstRunWizard(ctk.CTkToplevel):
    """หน้าต่างวิซาร์ดเริ่มต้นใช้งาน 4 ขั้นตอน"""

    def __init__(self, parent, on_finished_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.on_finished_callback = on_finished_callback
        self.current_step = 1

        self.title("วิซาร์ดเริ่มต้นใช้งาน - LINE Scheduler")
        self.geometry("620x520")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self._show_step(1)

    def _create_widgets(self):
        # Header Progress
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=25, pady=(20, 10))

        self.lbl_step_indicator = ctk.CTkLabel(
            self.header_frame,
            text="ขั้นตอนที่ 1 จาก 4",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3B82F6"
        )
        self.lbl_step_indicator.pack(anchor="w")

        self.lbl_step_title = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.lbl_step_title.pack(anchor="w", pady=(2, 0))

        # Content Frame
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(fill="both", expand=True, padx=25, pady=10)

        # Footer Buttons
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=25, pady=(5, 20))

        self.btn_prev = ctk.CTkButton(
            footer,
            text="< ย้อนกลับ",
            fg_color="#4B5563",
            hover_color="#6B7280",
            width=100,
            command=self._on_prev
        )
        self.btn_prev.pack(side="left")

        self.btn_next = ctk.CTkButton(
            footer,
            text="ถัดไป >",
            width=120,
            command=self._on_next
        )
        self.btn_next.pack(side="right")

    def _clear_content(self):
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _show_step(self, step: int):
        self.current_step = step
        self.lbl_step_indicator.configure(text=f"ขั้นตอนที่ {step} จาก 4")
        self._clear_content()

        self.btn_prev.configure(state="normal" if step > 1 else "disabled")
        self.btn_next.configure(text="เสร็จสิ้น" if step == 4 else "ถัดไป >")

        if step == 1:
            self._render_step_1()
        elif step == 2:
            self._render_step_2()
        elif step == 3:
            self._render_step_3()
        elif step == 4:
            self._render_step_4()

    # --- Step 1: ตรวจสอบความพร้อมของ LINE Desktop ---
    def _render_step_1(self):
        self.lbl_step_title.configure(text="ตรวจสอบความพร้อมของ LINE Desktop")

        lbl_desc = ctk.CTkLabel(
            self.content_frame,
            text="กรุณาตรวจสอบว่าคุณได้เปิดโปรแกรม LINE Desktop บนคอมพิวเตอร์\nเข้าสู่ระบบ และตั้งค่าการส่งข้อความด้วยปุ่ม Enter เรียบร้อยแล้ว",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(20, 15))

        self.status_box_step1 = ctk.CTkTextbox(self.content_frame, height=120)
        self.status_box_step1.pack(fill="x", padx=20, pady=(0, 10))

        btn_check = ctk.CTkButton(
            self.content_frame,
            text="ตรวจสอบสถานะเดี๋ยวนี้",
            command=self._check_step_1_status
        )
        btn_check.pack(padx=20, pady=(5, 10), anchor="w")
        self._check_step_1_status()

    def _check_step_1_status(self):
        self.status_box_step1.delete("1.0", "end")
        wins = get_all_line_windows()
        line_running = len(wins) > 0
        in_tray = False
        if not line_running:
            tray_h = find_line_tray_window()
            if tray_h:
                line_running = True
                in_tray = True
        session_unlocked = not is_session_locked()

        line_status_str = "เปิดใช้งานอยู่ (ในถาดระบบ Tray)" if in_tray else ("เปิดใช้งานอยู่" if line_running else "ไม่พบ LINE (กรุณาเปิดแอป)")
        self.status_box_step1.insert("end", f"[*] สถานะการทำงานของ LINE: {line_status_str}\n")
        self.status_box_step1.insert("end", f"[*] สถานะหน้าจอ Windows: {'ปลดล็อกปกติ' if session_unlocked else 'หน้าจอล็อกอยู่'}\n")
        self.status_box_step1.insert("end", "[*] การตั้งค่าที่จำเป็นใน LINE:\n    - Settings -> Chats -> Send message with: 'Enter'\n")

    # --- Step 2: เลือกห้องแชทเป้าหมาย ---
    def _render_step_2(self):
        self.lbl_step_title.configure(text="เลือกห้องแชทหรือกลุ่มทดสอบ")

        lbl_desc = ctk.CTkLabel(
            self.content_frame,
            text="ระบบรองรับทั้งค้นหาและเปิดห้องแชทให้อัตโนมัติ (Auto-Open) หรือเปิดแท็บแชทแยกไว้ล่วงหน้า\n(สามารถเลือกห้องจากรายการ หรือพิมพ์ชื่อเพื่อน/กลุ่มเป้าหมายได้โดยตรง)",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(20, 15))

        self.combo_step2_chat = ctk.CTkComboBox(self.content_frame, values=self._get_open_chats(), width=360)
        self.combo_step2_chat.pack(anchor="w", padx=20, pady=(0, 10))

        btn_rescan = ctk.CTkButton(
            self.content_frame,
            text="สแกนหาหน้าต่างใหม่",
            width=150,
            command=lambda: self.combo_step2_chat.configure(values=self._get_open_chats())
        )
        btn_rescan.pack(anchor="w", padx=20, pady=(0, 10))

    def _get_open_chats(self):
        wins = get_all_line_windows()
        if not wins:
            wake_line_from_tray()
            wins = get_all_line_windows()
        chats = [w['title'] for w in wins if not w['is_main']]
        return chats if chats else ["(ยังไม่พบหน้าต่างแยก - สามารถพิมพ์ชื่อห้องได้)"]

    # --- Step 3: ปรับแต่งพลังงานกันจอหลับ (Layer 2) ---
    def _render_step_3(self):
        self.lbl_step_title.configure(text="ตั้งค่าเครื่องให้พร้อมทำงาน 24 ชั่วโมง")

        lbl_desc = ctk.CTkLabel(
            self.content_frame,
            text="เพื่อให้มั่นใจว่าระบบจะส่งข้อความตรงเวลาแม้ทิ้งเครื่องไว้ข้ามคืน:\n- ปิด Sleep / จอดับ / Hibernate\n- ปิดการหลับเมื่อพับฝาโน้ตบุ๊ก\n- ปิด ScreenSaver อัตโนมัติ (มีปุ่มคืนค่าเดิมเสมอ)",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(20, 15))

        self.lbl_power_status = ctk.CTkLabel(self.content_frame, text="สถานะ: ยังไม่ได้ปรับแต่ง Power Plan", text_color="#F59E0B")
        self.lbl_power_status.pack(anchor="w", padx=20, pady=(0, 15))

        btn_apply_power = ctk.CTkButton(
            self.content_frame,
            text="ปรับแต่งเครื่องทันที (แนะนำ)",
            command=self._apply_power_setup
        )
        btn_apply_power.pack(anchor="w", padx=20, pady=(0, 10))

    def _apply_power_setup(self):
        ok = apply_optimized_power_settings()
        if ok:
            self.lbl_power_status.configure(text="สถานะ: ปรับแต่งเรียบร้อยแล้ว (เครื่องพร้อมรัน 24 ชม.)", text_color="#10B981")
        else:
            self.lbl_power_status.configure(text="สถานะ: ปรับแต่งบางส่วนไม่สำเร็จ (ตรวจสอบสิทธิ์)", text_color="#EF4444")

    # --- Step 4: ทดสอบส่งข้อความจริง ---
    def _render_step_4(self):
        self.lbl_step_title.configure(text="ทดสอบส่งข้อความจริง")

        lbl_desc = ctk.CTkLabel(
            self.content_frame,
            text="ทดสอบส่งข้อความจริงไปยังห้องแชทที่เลือกเพื่อยืนยันว่าการควบคุมทำงานสมบูรณ์",
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(20, 15))

        self.lbl_test_result = ctk.CTkLabel(self.content_frame, text="สถานะ: พร้อมกดทดสอบ", text_color="#9CA3AF")
        self.lbl_test_result.pack(anchor="w", padx=20, pady=(0, 15))

        btn_test_now = ctk.CTkButton(
            self.content_frame,
            text="ทดสอบส่งข้อความเข้าแชทเดี๋ยวนี้",
            command=self._execute_test_send
        )
        btn_test_now.pack(anchor="w", padx=20, pady=(0, 10))

    def _execute_test_send(self):
        target = getattr(self, "combo_step2_chat", None)
        chat_name = target.get() if target else "test-bot"
        if "(ยังไม่พบ" in chat_name:
            wins = get_all_line_windows()
            chats = [w['title'] for w in wins if not w['is_main']]
            chat_name = chats[0] if chats else "test-bot"

        self.lbl_test_result.configure(text=f"กำลังส่งข้อความไปยัง '{chat_name}'...", text_color="#3B82F6")
        self.update()

        sender = LineSender()
        msg = f"[LINE Scheduler Wizard Test]\nระบบตั้งค่าสำเร็จเรียบร้อย\nเวลา: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        res = sender.send_message(chat_name, msg, retry_count=1)

        if res.success:
            self.lbl_test_result.configure(text="สถานะ: ส่งสำเร็จเรียบร้อย (ตรวจสอบข้อความใน LINE ได้เลย)", text_color="#10B981")
        else:
            self.lbl_test_result.configure(text=f"สถานะ: ส่งไม่สำเร็จ ({res.error_message})", text_color="#EF4444")

    def _on_prev(self):
        if self.current_step > 1:
            self._show_step(self.current_step - 1)

    def _on_next(self):
        if self.current_step < 4:
            self._show_step(self.current_step + 1)
        else:
            if self.on_finished_callback:
                self.on_finished_callback()
            self.destroy()

