import os, hmac, hashlib, urllib.parse
from typing import Dict

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

def _telegram_secret_key() -> bytes:
    # per Telegram docs: secret_key = HMAC_SHA256("WebAppData", bot_token)
    return hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()

def parse_init_data(init_data: str) -> Dict[str, str]:
    # init_data — строка querystring от Telegram WebApp
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    return data

def check_init_data(init_data: str) -> Dict[str, str]:
    data = parse_init_data(init_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("No hash in init data")

    check_str = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])
    secret = _telegram_secret_key()
    calculated = hmac.new(secret, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("Invalid init data HMAC")

    return data
