import hmac
import hashlib
from urllib.parse import parse_qsl
import time

def check_telegram_webapp_auth(init_data: str, bot_token: str) -> dict | None:
    print(f"Received init_data: {init_data}")

    data = dict(parse_qsl(init_data))
    print(f"Parsed data: {data}")

    hash_ = data.pop("hash", None)
    if not hash_:
        print("No hash found in data")
        return None
    print(f"Extracted hash: {hash_}")

    # Формируем data_check_string
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    print(f"Data check string:\n{data_check_string}")

    # Секретный ключ = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    print(f"Secret key (HMAC SHA256 of bot_token with 'WebAppData'): {secret_key.hex()}")

    # Вычисляем хэш
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    print(f"Computed hash: {computed_hash}")
    print(f"Given hash: {hash_}")

    if computed_hash != hash_:
        print("Hash mismatch, invalid init_data")
        return None

    # Проверка времени
    auth_date = int(data.get("auth_date", 0))
    now = int(time.time())
    print(f"auth_date from data: {auth_date}")
    print(f"Current time: {now}")
    if abs(now - auth_date) > 86400:
        print("auth_date is too old")
        return None

    print("Telegram Mini App auth data is valid")
    return data