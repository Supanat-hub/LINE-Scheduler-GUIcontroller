"""
Logging and diagnostic screenshot utility for LINE Scheduler
"""

import sys
import logging
from datetime import datetime
from pathlib import Path
from PIL import ImageGrab

from app.config import LOGS_DIR, SCREENSHOTS_DIR

# Ensure UTF-8 output on Windows consoles when running interactively
if sys.stdout is not None:
    try:
        if getattr(sys.stdout, 'encoding', None) and sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr is not None and getattr(sys.stderr, 'encoding', None) and sys.stderr.encoding.lower() != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def setup_logger(name: str = "line_scheduler") -> logging.Logger:
    """สร้างหรือดึง Logger ที่บันทึกลงไฟล์และแสดงผลบน Console (ถ้ามี)"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File Handler
    log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler (เฉพาะเมื่อมี stdout เช่น เมื่อรันผ่าน command line)
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def capture_screenshot(prefix: str = "failure") -> Path | None:
    """จับภาพหน้าจอปัจจุบันและบันทึกลงโฟลเดอร์ screenshots สำหรับการตรวจสอบข้อผิดพลาด"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = SCREENSHOTS_DIR / filename
        
        screenshot = ImageGrab.grab(all_screens=True)
        screenshot.save(filepath, "PNG")
        logger.info(f"บันทึกภาพหน้าจอตรวจสอบแล้ว: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"ไม่สามารถจับภาพหน้าจอได้: {e}")
        return None

