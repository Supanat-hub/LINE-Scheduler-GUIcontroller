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
    """ทดสอบกรณีเรียกคำสั่ง PowerShell สำเร็จ"""
    mock_res = MagicMock()
    mock_res.returncode = 0
    with patch("subprocess.run", return_value=mock_res) as mock_run:
        ok, msg = add_defender_exclusion(target_dir=Path(r"C:\TestPath"))
        assert ok is True
        assert "เรียบร้อย" in msg
        mock_run.assert_called_once()
        print("[OK] Test 1: add_defender_exclusion successful mock passed")


def test_add_defender_exclusion_failure():
    """ทดสอบกรณีคำสั่งล้มเหลว"""
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stderr = "Access is denied"
    with patch("subprocess.run", return_value=mock_res):
        ok, msg = add_defender_exclusion(target_dir=Path(r"C:\TestPath"))
        assert ok is False
        assert "Access is denied" in msg
        print("[OK] Test 2: add_defender_exclusion failure handled correctly")


if __name__ == "__main__":
    test_add_defender_exclusion_success()
    test_add_defender_exclusion_failure()
    print("\n[SUCCESS] All Defender Tests Passed!")

