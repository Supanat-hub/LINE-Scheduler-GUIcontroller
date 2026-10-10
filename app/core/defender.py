"""
Windows Defender Antivirus Exclusion Management Module (Strictly NO emojis used)
"""

import sys
import ctypes
import base64
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from app.core.logger import logger


def add_defender_exclusion(
    target_dir: Optional[Path] = None,
    process_name: str = "LineScheduler.exe"
) -> Tuple[bool, str]:
    """
    เรียกคำสั่ง PowerShell แบบขอสิทธิ์ Administrator (UAC RunAs)
    เพื่อเพิ่มโฟลเดอร์โปรแกรมและชื่อโปรเซสเข้าสู่ข้อยกเว้นของ Windows Defender
    ใช้ Base64 -EncodedCommand เพื่อป้องกันปัญหาการ Escape เครื่องหมายคำพูดและ Backslash
    """
    if target_dir is None:
        if getattr(sys, 'frozen', False):
            target_dir = Path(sys.executable).resolve().parent
        else:
            target_dir = Path(__file__).resolve().parent.parent.parent

    # ตัด Backslash ท้ายโฟลเดอร์ออกเสมอ เพื่อป้องกันปัญหาการ Escape ใน PowerShell
    target_path_str = str(target_dir).rstrip("\\").replace("'", "''")

    ps_command = (
        f"Add-MpPreference -ExclusionPath '{target_path_str}'; "
        f"Add-MpPreference -ExclusionProcess '{process_name}'"
    )
    encoded_cmd = base64.b64encode(ps_command.encode("utf-16le")).decode("ascii")

    logger.info(f"กำลังร้องขอสิทธิ์ Administrator เพื่อเพิ่ม Exclusion: {target_path_str}")

    # วิธีหลัก: เรียกผ่าน ShellExecuteW ของ Windows API โดยตรง (ปราศจากปัญหาการแยกพารามิเตอร์)
    try:
        params = f"-NoProfile -WindowStyle Hidden -EncodedCommand {encoded_cmd}"
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 0)
        # ShellExecuteW คืนค่า > 32 เมื่อคำสั่งถูกส่งไปยังระบบสำเร็จ
        if ret > 32:
            logger.info("ส่งคำขอสิทธิ์ Administrator เพิ่มข้อยกเว้น Windows Defender ผ่าน ShellExecute สำเร็จ")
            return True, "ส่งคำขอเพิ่มข้อยกเว้นไปยังระบบเรียบร้อย (กรุณากด 'Yes' ที่หน้าต่าง UAC)"
        elif ret == 5:  # SE_ERR_ACCESSDENIED
            logger.warning("ผู้ใช้ยกเลิกการอนุญาตสิทธิ์ Administrator ที่หน้าต่าง UAC")
            return False, "ผู้ใช้ยกเลิกการอนุญาตสิทธิ์ Administrator ที่หน้าต่าง UAC"
    except Exception as e_shell:
        logger.warning(f"ShellExecuteW ไม่สำเร็จ กำลังใช้ subprocess: {e_shell}")

    # วิธีสำรอง: เรียกผ่าน Start-Process พร้อม -EncodedCommand
    try:
        launcher = (
            f"Start-Process powershell.exe -Verb RunAs "
            f"-ArgumentList '-NoProfile -WindowStyle Hidden -EncodedCommand {encoded_cmd}'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", launcher],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            logger.info("ส่งคำสั่งเพิ่มข้อยกเว้น Windows Defender เรียบร้อย")
            return True, "ส่งคำขอเพิ่มข้อยกเว้นไปยังระบบเรียบร้อย (กรุณากด 'Yes' ที่หน้าต่าง UAC)"
        else:
            err_msg = result.stderr.strip() if result.stderr else "ไม่สามารถส่งคำขอ UAC ได้"
            logger.warning(f"เรียกคำสั่ง Exclusion ไม่สำเร็จ: {err_msg}")
            return False, f"เกิดข้อผิดพลาด: {err_msg}"
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเรียก Add-MpPreference: {e}")
        return False, str(e)


