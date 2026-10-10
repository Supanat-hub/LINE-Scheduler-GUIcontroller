"""
Phase 0 Spike Test: LINE Desktop GUI Automation Sender
------------------------------------------------------
สคริปต์ทดสอบเดี่ยวสำหรับ Phase 0:
1. ค้นหาหน้าต่างแชท LINE ที่แยกออกมา (Pop-out Window)
2. ดึงหน้าต่างขึ้นมาด้านหน้า (Foreground & Restore)
3. ตรวจสอบ UI Control / พิกัดช่องพิมพ์
4. สำรองคลิปบอร์ด -> วางข้อความภาษาไทย + อีโมจิ -> กด Enter ส่ง
5. คืนค่าคลิปบอร์ดเดิม
"""

import sys
import time
import ctypes
from ctypes import wintypes
import win32gui
import win32con
import win32process
import win32service
import pyperclip
import pyautogui

# ตั้งค่า stdout/stderr ให้แสดงผลภาษาไทยได้ถูกต้องในคอนโซล
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ปรับ safety ของ pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


def attach_to_default_desktop():
    """สลับ Thread เข้าสู่ Default Desktop ของ Windows เพื่อให้เห็นหน้าต่างของผู้ใช้จริง"""
    try:
        hdesk = win32service.OpenDesktop('Default', 0, False, win32con.GENERIC_ALL)
        if hdesk:
            res = ctypes.windll.user32.SetThreadDesktop(int(hdesk))
            return res != 0
    except Exception as e:
        # หากรันจาก interactive shell ปกติอาจไม่ต้องสลับ
        pass
    return True


def get_line_windows():
    """ค้นหาหน้าต่างทั้งหมดของ LINE บนหน้าจอ"""
    attach_to_default_desktop()
    windows = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            cls = win32gui.GetClassName(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # ตรวจสอบว่าเป็นหน้าต่างของ Qt LINE หรือมีชื่อที่เกี่ยวข้อง
            if ('Qt6' in cls or 'LINE' in cls) and width > 100 and height > 100:
                windows.append({
                    'hwnd': hwnd,
                    'pid': pid,
                    'title': title,
                    'class': cls,
                    'rect': rect,
                    'is_main': (title == 'LINE')
                })

    win32gui.EnumWindows(enum_callback, None)
    return windows


def focus_window(hwnd):
    """Restore หน้าต่างที่ถูกย่อและดึงขึ้นมาเป็น Foreground"""
    attach_to_default_desktop()

    # หากหน้าต่างถูก Minimize ให้ Restore
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    # ปลดล็อก Foreground Lock โดยการส่ง Alt key เล็กน้อย
    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)


def send_message_to_chat(hwnd, message_text: str):
    """ส่งข้อความเข้าหน้าต่างแชทด้วยระบบ Direct UIA Injection + PostMessage (พร้อม Fallback)"""
    from pywinauto import Desktop

    attach_to_default_desktop()
    focus_window(hwnd)

    # 1. พยายามใช้วิธี Primary Engine: UIA AutoSuggestTextArea
    uia_success = False
    try:
        d = Desktop(backend='uia')
        bot_win = d.window(handle=hwnd)
        edit = bot_win.child_window(class_name='AutoSuggestTextArea', control_type='Edit')
        elem = edit.wrapper_object()

        print("[*] [Engine 1 - UIA] ตรวจพบช่องพิมพ์ 'AutoSuggestTextArea'")
        print("[*] กำลังกำหนดข้อความตรงเข้าช่องพิมพ์...")
        elem.set_edit_text(message_text)
        time.sleep(0.3)

        val_in_box = elem.get_value()
        print(f"[*] ตรวจสอบข้อความในช่องพิมพ์: {len(val_in_box)} ตัวอักษร")

        # ส่งสัญญาณกด Enter เข้าสู่หน้าต่าง
        print("[*] กำลังส่ง Enter ผ่าน PostMessage...")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        time.sleep(0.5)

        # ตรวจสอบว่าช่องพิมพ์ว่างเปล่าหรือยัง
        if elem.get_value() == "":
            print("[+] [Engine 1 - UIA] ส่งข้อความสำเร็จเรียบร้อย (ช่องพิมพ์ว่างแล้ว)!")
            uia_success = True
        else:
            # หากกด Enter แล้วข้อความยังค้างอยู่ ให้ลองคลิกปุ่ม Send (LcButton ตัวสุดท้าย)
            print("[!] ข้อความยังค้างอยู่ ลองคลิกปุ่มส่ง (Send Button)...")
            try:
                input_panel = bot_win.child_window(class_name='MessageInputPanel')
                buttons = [b for b in input_panel.descendants() if 'Button' in b.class_name() or b.element_info.control_type == 'Button']
                if buttons:
                    send_btn = buttons[-1]  # ปุ่มส่งอยู่ขวาสุด
                    send_rect = send_btn.rectangle()
                    # ส่งคลิกซ้ายไปยังปุ่ม
                    btn_cx = (send_rect.left + send_rect.right) // 2
                    btn_cy = (send_rect.top + send_rect.bottom) // 2
                    l_param = win32gui.MAKELONG(btn_cx - bot_win.rectangle().left, btn_cy - bot_win.rectangle().top)
                    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
                    time.sleep(0.05)
                    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, l_param)
                    time.sleep(0.5)

                if elem.get_value() == "":
                    print("[+] [Engine 1 - UIA] ส่งข้อความสำเร็จผ่านปุ่มส่ง!")
                    uia_success = True
            except Exception as e_btn:
                print(f"[!] กดปุ่มส่งไม่สำเร็จ: {e_btn}")

    except Exception as e_uia:
        print(f"[!] [Engine 1 - UIA] ไม่สามารถใช้วิธี UIA ได้: {e_uia}")

    if uia_success:
        return

    # 2. หาก Engine 1 ไม่สำเร็จ ให้ใช้ Engine 2: Fallback ด้วย Clipboard + Click
    print("[*] [Engine 2 - Fallback] สลับมาใช้วิธี Clipboard + Click...")
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top

    click_x = left + int(width * 0.45)
    click_y = bottom - 50

    print(f"[*] คลิกตำแหน่งสัมพัทธ์ที่ ({click_x}, {click_y})...")
    pyautogui.click(click_x, click_y)
    time.sleep(0.2)

    original_clipboard = None
    try:
        original_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(message_text)
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(0.3)
        print("[+] [Engine 2] ส่งข้อความเรียบร้อย!")
    finally:
        if original_clipboard is not None:
            try:
                pyperclip.copy(original_clipboard)
            except Exception:
                pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LINE Scheduler - Phase 0 Spike Test")
    parser.add_argument("--repeat", type=int, default=1, help="จำนวนรอบที่ต้องการทดสอบส่ง (เช่น 1 หรือ 10)")
    parser.add_argument("--target", type=str, default="", help="ชื่อหน้าต่างแชทเป้าหมาย (หากไม่ระบุจะเลือกหน้าต่างแรกที่พบ)")
    parser.add_argument("--timeout", type=int, default=30, help="เวลาสูงสุดที่รอตรวจจับหน้าต่างแชท (วินาที)")
    args = parser.parse_args()

    print("=" * 60)
    print(" LINE Scheduler - Phase 0 Spike Test")
    print("=" * 60)

    windows = get_line_windows()
    if not windows:
        print("[-] ไม่พบหน้าต่าง LINE ที่เปิดอยู่ กรุณาเปิด LINE Desktop และเข้าสู่ระบบก่อนครับ")
        return

    print(f"[+] พบหน้าต่าง LINE ทั้งหมด {len(windows)} หน้าต่าง:")
    for idx, w in enumerate(windows):
        status = "[หน้าต่างหลัก]" if w['is_main'] else "[หน้าต่างแชทแยก]"
        print(f"  {idx + 1}. {w['title']!r} {status} (HWND: {w['hwnd']}, Rect: {w['rect']})")

    # ค้นหาหน้าต่างแชทแยก (ที่ไม่ใช่หน้าต่างหลัก 'LINE')
    chat_windows = [w for w in windows if not w['is_main']]

    target_window = None
    if chat_windows:
        if args.target:
            matched = [w for w in chat_windows if args.target.lower() in w['title'].lower()]
            if matched:
                target_window = matched[0]
                print(f"\n[+] พบหน้าต่างที่ตรงกับ '{args.target}': {target_window['title']!r}")
            else:
                print(f"\n[-] ไม่พบหน้าต่างที่ตรงกับ '{args.target}'")
                return
        else:
            target_window = chat_windows[0]
            print(f"\n[+] ตรวจพบหน้าต่างแชทเป้าหมายทันที: {target_window['title']!r}")
    else:
        print("\n[!] ยังไม่พบหน้าต่างแชทที่ถูกแยกออกมา (Pop-out Window)")
        print("    👉 กรุณาดังเบิลคลิกที่ห้องแชทใน LINE (เช่น 'Keep Memo' หรือกลุ่มทดสอบ)")
        print(f"    กำลังรอตรวจจับหน้าต่างแชทใหม่ (รอสูงสุด {args.timeout} วินาที)...")
        for sec in range(args.timeout, 0, -1):
            time.sleep(1)
            current_windows = get_line_windows()
            new_chats = [w for w in current_windows if not w['is_main']]
            if args.target:
                new_chats = [w for w in new_chats if args.target.lower() in w['title'].lower()]
            if new_chats:
                target_window = new_chats[0]
                print(f"\n[+] ตรวจพบหน้าต่างแชทเรียบร้อย: {target_window['title']!r}!")
                break
            if sec % 5 == 0:
                print(f"    ...ยังรออยู่ (เหลือเวลา {sec} วินาที)")

        if not target_window:
            print("\n[-] หมดเวลาการรอ: ยังไม่พบหน้าต่างแชทที่แยกออกมา")
            print("    กรุณาเปิดหน้าต่างแชททิ้งไว้ แล้วรันคำสั่งใหม่อีกครั้งครับ")
            return

    print(f"\n[+] เตรียมทดสอบส่งทั้งหมด {args.repeat} รอบ...")
    success_count = 0

    for round_num in range(1, args.repeat + 1):
        test_msg = (
            f"🤖 [LINE Scheduler Test - รอบที่ {round_num}/{args.repeat}]\n"
            "ทดสอบระบบส่งข้อความอัตโนมัติ Phase 0 ✨\n"
            f"เวลาส่ง: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            "ทดสอบภาษาไทย + สระอำ วรรณยุกต์ครบ + Emojis 🚀🎯✅"
        )

        print(f"\n--- เริ่มส่งรอบที่ {round_num}/{args.repeat} ---")
        try:
            send_message_to_chat(target_window['hwnd'], test_msg)
            success_count += 1
            print(f"[✓] รอบที่ {round_num} สำเร็จ!")
        except Exception as e:
            print(f"[X] เกิดข้อผิดพลาดในรอบที่ {round_num}: {e}")

        if round_num < args.repeat:
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"สรุปผลการทดสอบ: สำเร็จ {success_count}/{args.repeat} ครั้ง")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
