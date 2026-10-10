"""
Main Application Entrypoint for LINE Scheduler
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure early desktop attachment before importing GUI/UIA modules
import app
from app.core.logger import logger
from app.ui.main_window import MainWindow


def main():
    logger.info("กำลังเริ่มต้นโปรแกรม LINE Scheduler...")
    try:
        app_window = MainWindow()
        logger.info("หน้าต่างหลักพร้อมทำงาน เริ่มต้น Mainloop")
        app_window.mainloop()
    except Exception as e:
        logger.critical(f"เกิดข้อผิดพลาดร้ายแรง: {e}", exc_info=True)
    finally:
        logger.info("ปิดโปรแกรม LINE Scheduler เรียบร้อย")


if __name__ == "__main__":
    main()

