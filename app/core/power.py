"""
Power and Screen Lock Prevention Module (Layers 1 - 3)
"""

import sys
import os
import json
import subprocess
import ctypes
import winreg
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import DATA_DIR
from app.core.logger import logger

# Win32 Constants for SetThreadExecutionState
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

POWER_BACKUP_FILE = DATA_DIR / "power_backup.json"
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "LineScheduler"


# ==========================================
# Layer 1: Runtime Keep-Awake (No Admin)
# ==========================================

def enable_runtime_keep_awake() -> bool:
    """
    ป้องกันเครื่อง Sleep, จอดับ และ ScreenSaver ในขณะที่โปรแกรมทำงานอยู่
    (ไม่ต้องใช้สิทธิ์ Admin และจะคืนค่าเดิมอัตโนมัติเมื่อโปรแกรมปิดตัวลง)
    """
    try:
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        prev_state = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if prev_state != 0:
            logger.info("เปิดใช้งาน Keep-Awake ชั้นที่ 1 เรียบร้อย (เครื่องและจอจะไม่หลับขณะโปรแกรมเปิดอยู่)")
            return True
        else:
            logger.warning("SetThreadExecutionState คืนค่า 0 (อาจไม่ได้รับการรองรับ)")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเปิด Keep-Awake ชั้นที่ 1: {e}")
    return False


def disable_runtime_keep_awake() -> bool:
    """คืนค่าโหมดการใช้พลังงานกลับสู่ปกติของ Windows"""
    try:
        flags = ES_CONTINUOUS
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
        logger.info("คืนค่าการจัดการพลังงานชั้นที่ 1 กลับสู่ปกติเรียบร้อย")
        return True
    except Exception as e:
        logger.error(f"คืนค่าการจัดการพลังงานล้มเหลว: {e}")
    return False


# ==========================================
# Layer 2: System Power & ScreenSaver Settings
# ==========================================

def backup_current_power_settings() -> Dict[str, Any]:
    """สำรองค่าการตั้งค่าหน้าจอและ ScreenSaver ปัจจุบันลงไฟล์ JSON ก่อนแก้ไข"""
    backup_data = {
        "screensaver_active": "1",
        "screensaver_secure": "1",
        "screensaver_timeout": "600",
        "backed_up_at": str(ctypes.c_longlong(0).value)
    }

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, "ScreenSaveActive")
                backup_data["screensaver_active"] = str(val)
            except FileNotFoundError:
                pass

            try:
                val, _ = winreg.QueryValueEx(key, "ScreenSaverIsSecure")
                backup_data["screensaver_secure"] = str(val)
            except FileNotFoundError:
                pass

            try:
                val, _ = winreg.QueryValueEx(key, "ScreenSaveTimeOut")
                backup_data["screensaver_timeout"] = str(val)
            except FileNotFoundError:
                pass
    except Exception as e:
        logger.warning(f"อ่านค่า Registry เพื่อสำรองข้อมูลไม่สำเร็จ: {e}")

    try:
        POWER_BACKUP_FILE.write_text(json.dumps(backup_data, indent=2), encoding="utf-8")
        logger.info(f"สำรองค่าพลังงานเดิมเรียบร้อยที่: {POWER_BACKUP_FILE}")
    except Exception as e:
        logger.error(f"บันทึกไฟล์สำรองพลังงานล้มเหลว: {e}")

    return backup_data


def apply_optimized_power_settings() -> bool:
    """
    ชั้นที่ 2: ปรับแต่ง Power Plan ของเครื่องให้พร้อมรัน 24 ชม.
    - ปิด Sleep, Hibernate, จอดับ ทั้งตอนเสียบปลั๊กและใช้แบตเตอรี่
    - ปิดการ Sleep เมื่อปิดฝาโน้ตบุ๊ก (Lid Close = Do nothing)
    - ปิด ScreenSaver และการล็อกหน้าจอเมื่อไม่มีการใช้งาน
    """
    # 1. สำรองข้อมูลเดิมก่อนเสมอ
    if not POWER_BACKUP_FILE.exists():
        backup_current_power_settings()

    success = True

    # 2. คำสั่ง powercfg
    powercfg_cmds = [
        "powercfg /change standby-timeout-ac 0",
        "powercfg /change standby-timeout-dc 0",
        "powercfg /change monitor-timeout-ac 0",
        "powercfg /change monitor-timeout-dc 0",
        "powercfg /change hibernate-timeout-ac 0",
        "powercfg /change hibernate-timeout-dc 0",
        # ปิดฝาโน้ตบุ๊กแล้วไม่ต้องหลับ (0 = Do nothing)
        "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0",
        "powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0",
        "powercfg /setactive SCHEME_CURRENT"
    ]

    for cmd in powercfg_cmds:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode != 0:
                logger.warning(f"รันคำสั่ง '{cmd}' แจ้งเตือน: {res.stderr.strip()}")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการรัน '{cmd}': {e}")
            success = False

    # 3. ปรับแต่ง Registry เพื่อปิด ScreenSaver
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ScreenSaveActive", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(key, "ScreenSaverIsSecure", 0, winreg.REG_SZ, "0")
        logger.info("ปิดการทำงานของ ScreenSaver ใน Registry เรียบร้อย")
    except Exception as e:
        logger.error(f"แก้ไข Registry ปิด ScreenSaver ไม่สำเร็จ: {e}")
        success = False

    return success


def restore_original_power_settings() -> bool:
    """คืนค่าการตั้งค่าพลังงานและ ScreenSaver ดั้งเดิมจากไฟล์สำรอง"""
    if not POWER_BACKUP_FILE.exists():
        logger.warning("ไม่พบไฟล์สำรองค่าพลังงานเดิม ไม่สามารถคืนค่าได้")
        return False

    try:
        data = json.loads(POWER_BACKUP_FILE.read_text(encoding="utf-8"))
        # คืนค่า Registry ScreenSaver
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
            if "screensaver_active" in data:
                winreg.SetValueEx(key, "ScreenSaveActive", 0, winreg.REG_SZ, data["screensaver_active"])
            if "screensaver_secure" in data:
                winreg.SetValueEx(key, "ScreenSaverIsSecure", 0, winreg.REG_SZ, data["screensaver_secure"])
            if "screensaver_timeout" in data:
                winreg.SetValueEx(key, "ScreenSaveTimeOut", 0, winreg.REG_SZ, data["screensaver_timeout"])

        # คืนค่า Power Plan มาตรฐาน (สมดุล)
        subprocess.run("powercfg /restoredefaultschemes", shell=True, capture_output=True)
        logger.info("คืนค่า Power Plan และ ScreenSaver ดั้งเดิมเรียบร้อย")

        POWER_BACKUP_FILE.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.error(f"คืนค่าพลังงานเดิมล้มเหลว: {e}")
        return False


# ==========================================
# Layer 3: Auto-start with Windows (Startup)
# ==========================================

def clean_legacy_startup_shortcut() -> None:
    """ลบ Shortcut เก่าในโฟลเดอร์ Startup เพื่อไม่ให้เกิดการเปิดโปรแกรมซ้ำ 2 ครั้งร่วมกับ Registry Run"""
    try:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            startup_dir = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Startup"
            for lnk_name in ["LINE Scheduler.lnk", "LineScheduler.lnk"]:
                lnk_file = startup_dir / lnk_name
                if lnk_file.exists():
                    lnk_file.unlink(missing_ok=True)
                    logger.info(f"ลบ Shortcut ในโฟลเดอร์ Startup ที่ซ้ำซ้อนเรียบร้อย: {lnk_file}")
    except Exception as e:
        logger.warning(f"ลบ Startup shortcut เก่าไม่สำเร็จ: {e}")


def set_startup_enabled(enable: bool, executable_path: Optional[str] = None) -> bool:
    """
    ชั้นที่ 3: เปิดหรือปิดให้โปรแกรมทำงานอัตโนมัติเมื่อเปิดเครื่อง (At Log on)
    """
    # เคลียร์ Shortcut เก่าในโฟลเดอร์ Startup ทุกครั้งเพื่อป้องกันการเปิดซ้ำ
    clean_legacy_startup_shortcut()

    if executable_path is None:
        if getattr(sys, 'frozen', False):
            executable_path = f'"{sys.executable}"'
        else:
            executable_path = f'"{sys.executable}" "{Path(__file__).resolve().parent.parent / "main.py"}"'

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, executable_path)
                logger.info(f"เปิดใช้งาน Auto-start สำเร็จ: {executable_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    logger.info("ปิดใช้งาน Auto-start เรียบร้อย")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        logger.error(f"ตั้งค่า Auto-start ใน Registry ล้มเหลว: {e}")
        return False


def is_startup_enabled() -> bool:
    """ตรวจสอบว่ามีการลงทะเบียน Auto-start ไว้หรือไม่"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_REG_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"ตรวจสอบสถานะ Auto-start ล้มเหลว: {e}")
        return False

