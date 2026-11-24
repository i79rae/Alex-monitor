import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_NAME = os.getenv("BOT_NAME", "My Radar")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "40"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "10"))
MAX_RADARS = int(os.getenv("MAX_RADARS_PER_USER", "20"))
DB_PATH = os.getenv("DB_PATH", "radar.db")
SUPPORT_URL = os.getenv("SUPPORT_URL", "")
PROXIES = [p.strip() for p in os.getenv("PROXIES", "").split(",") if p.strip()]
FONT_PATH = os.getenv("FONT_PATH", "")
