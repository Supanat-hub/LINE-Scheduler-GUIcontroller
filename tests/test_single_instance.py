"""
Unit tests for Single Instance Mutex and Startup cleanup logic (No emojis)
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.single_instance import ensure_single_instance, ERROR_ALREADY_EXISTS
from app.core.power import clean_legacy_startup_shortcut


def test_single_instance_first_run():
    """ทดสอบกรณีรันครั้งแรก (ไม่พบ Instance เดิม) ต้องคืนค่า True"""
    with patch("ctypes.windll.kernel32.CreateMutexW", return_value=12345), \
         patch("ctypes.windll.kernel32.GetLastError", return_value=0):
        assert ensure_single_instance() is True
        print("[OK] test_single_instance_first_run passed")


def test_single_instance_duplicate_blocked():
    """ทดสอบกรณีพบ Instance เดิมอยู่แล้ว (ERROR_ALREADY_EXISTS) ต้องคืนค่า False"""
    with patch("ctypes.windll.kernel32.CreateMutexW", return_value=12345), \
         patch("ctypes.windll.kernel32.GetLastError", return_value=ERROR_ALREADY_EXISTS), \
         patch("app.core.single_instance._restore_existing_window") as mock_restore:
        assert ensure_single_instance() is False
        mock_restore.assert_called_once()
        print("[OK] test_single_instance_duplicate_blocked passed")


def test_clean_legacy_startup_shortcut():
    """ทดสอบการลบ Shortcut เก่าในโฟลเดอร์ Startup"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_startup = Path(tmpdir) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        mock_startup.mkdir(parents=True, exist_ok=True)
        test_lnk = mock_startup / "LINE Scheduler.lnk"
        test_lnk.write_text("dummy shortcut", encoding="utf-8")
        assert test_lnk.exists()

        with patch.dict(os.environ, {"APPDATA": tmpdir}):
            clean_legacy_startup_shortcut()
            assert not test_lnk.exists()
            print("[OK] test_clean_legacy_startup_shortcut passed")


if __name__ == "__main__":
    test_single_instance_first_run()
    test_single_instance_duplicate_blocked()
    test_clean_legacy_startup_shortcut()
    print("\n[SUCCESS] All Single Instance and Startup Tests Passed!")

