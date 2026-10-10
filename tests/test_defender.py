"""
Test suite for Windows Defender exclusion logic (No emojis)
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.defender import add_defender_exclusion


def test_add_defender_exclusion_success():
    """ทดสอบกรณีเรียกผ่าน ShellExecuteW สำเร็จ (>32)"""
    with patch("ctypes.windll.shell32.ShellExecuteW", return_value=42) as mock_shell:
        ok, msg = add_defender_exclusion(target_dir=Path(r"C:\TestPath"))
        assert ok is True
        assert "เรียบร้อย" in msg
        mock_shell.assert_called_once()
        print("[OK] Test 1: add_defender_exclusion ShellExecuteW success passed")


def test_add_defender_exclusion_uac_cancelled():
    """ทดสอบกรณีผู้ใช้กดยกเลิก UAC (code 5)"""
    with patch("ctypes.windll.shell32.ShellExecuteW", return_value=5):
        ok, msg = add_defender_exclusion(target_dir=Path(r"C:\TestPath"))
        assert ok is False
        assert "ยกเลิก" in msg
        print("[OK] Test 2: add_defender_exclusion UAC cancelled handled correctly")


def test_add_defender_exclusion_subprocess_fallback():
    """ทดสอบกรณี ShellExecute ล้มเหลวแล้ว Fallback ไปยัง subprocess"""
    mock_res = MagicMock()
    mock_res.returncode = 0
    with patch("ctypes.windll.shell32.ShellExecuteW", side_effect=Exception("API error")), \
         patch("subprocess.run", return_value=mock_res) as mock_run:
        ok, msg = add_defender_exclusion(target_dir=Path(r"C:\TestPath"))
        assert ok is True
        assert "เรียบร้อย" in msg
        mock_run.assert_called_once()
        print("[OK] Test 3: add_defender_exclusion subprocess fallback passed")


if __name__ == "__main__":
    test_add_defender_exclusion_success()
    test_add_defender_exclusion_uac_cancelled()
    test_add_defender_exclusion_subprocess_fallback()
    print("\n[SUCCESS] All Defender Tests Passed!")

