import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "tickets.db"


def load_config() -> tuple[str, int]:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    raw_chat_id = (os.getenv("SUPPORT_CHAT_ID") or "").strip()

    if not token:
        raise SystemExit("В файле .env не задан BOT_TOKEN.")
    try:
        chat_id = int(raw_chat_id)
    except ValueError:
        raise SystemExit("SUPPORT_CHAT_ID должен быть числом, например -1003888015937.")
    return token, chat_id


BOT_TOKEN, SUPPORT_CHAT_ID = load_config()