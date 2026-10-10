"""
Windows Defender Antivirus Exclusion Management Module (Strictly NO emojis used)
"""

import sys
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
    """
    if target_dir is None:
        if getattr(sys, 'frozen', False):
            target_dir = Path(sys.executable).resolve().parent
        else:
            target_dir = Path(__file__).resolve().parent.parent.parent

    target_path_str = str(target_dir).replace("'", "''")

    ps_command = (
        f"Add-MpPreference -ExclusionPath '{target_path_str}'; "
        f"Add-MpPreference -ExclusionProcess '{process_name}'"
    )

    launcher = (
        f"Start-Process powershell -Verb RunAs "
        f"-ArgumentList \"-NoProfile -WindowStyle Hidden -Command \\\"{ps_command}\\\"\""
    )

    try:
        logger.info(f"กำลังร้องขอสิทธิ์ Administrator เพื่อเพิ่ม Exclusion: {target_path_str}")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", launcher],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            logger.info("ส่งคำสั่งเพิ่มข้อยกเว้น Windows Defender เรียบร้อย")
            return True, "ส่งคำขอเพิ่มข้อยกเว้นไปยังระบบเรียบร้อย (กด 'Yes' ที่หน้าต่าง UAC)"
        else:
            logger.warning(f"เรียกคำสั่ง Exclusion ไม่สำเร็จ: {result.stderr}")
            return False, f"เกิดข้อผิดพลาด: {result.stderr.strip()}"
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเรียก Add-MpPreference: {e}")
        return False, str(e)

