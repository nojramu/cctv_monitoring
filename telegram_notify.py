import os
from datetime import datetime

import requests


ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _load_env_file(file_path):
    """Load simple KEY=VALUE pairs from a local env file into process env."""
    if not os.path.exists(file_path):
        return

    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _telegram_config():
    _load_env_file(ENV_FILE)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return token, chat_id


def send_telegram_message(message):
    token, chat_id = _telegram_config()
    if not token or not chat_id:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram message error: {e}")
        return False


def send_telegram_photo(image_path, caption=None):
    token, chat_id = _telegram_config()
    if not token or not chat_id:
        print("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    if not os.path.isfile(image_path):
        print(f"Telegram photo error: file not found: {image_path}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "Markdown"

    try:
        with open(image_path, "rb") as photo_file:
            files = {"photo": photo_file}
            response = requests.post(url, data=payload, files=files, timeout=30)
            response.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram photo error: {e}")
        return False


def send_motion_alert(image_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = f"*Motion detected*\nTime: {now}"
    return send_telegram_photo(image_path, caption=caption)


if __name__ == "__main__":
    send_telegram_message("*Pi 5 System Alert:* Telegram notifier is running.")