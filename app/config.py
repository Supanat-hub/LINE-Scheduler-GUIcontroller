"""
Configuration settings for LINE Scheduler
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
DB_PATH = DATA_DIR / "scheduler.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Sender Defaults
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY_SEC = 20.0
POST_FOCUS_DELAY_SEC = 0.3
POST_INPUT_DELAY_SEC = 0.3
POST_SEND_DELAY_SEC = 0.5

# Application Info
APP_NAME = "LINE Scheduler"
APP_VERSION = "1.0.3"

