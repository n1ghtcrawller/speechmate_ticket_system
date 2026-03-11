from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from dotenv import load_dotenv
import os


load_dotenv()

# Токен бота: сначала берём API_TOKEN (на случай старых конфигов),
# иначе BOT_TOKEN (как в текущем .env)
API_TOKEN = os.getenv("API_TOKEN") or os.getenv("BOT_TOKEN")

SFTP_HOST = os.getenv("SFTP_HOST")
SFTP_PORT = int(os.getenv("SFTP_PORT")) if os.getenv("SFTP_PORT") is not None else None
SFTP_USER = os.getenv("SFTP_USER")
SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
SFTP_DIRECTORY = os.getenv("SFTP_DIRECTORY")

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT")) if os.getenv("MQTT_PORT") is not None else None
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./support_bot.db"

    SECRET_KEY: str = "supersecretkey"
    BOT_TOKEN: Optional[str] = None
    media_path: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
   
    # Игнорируем лишние переменные из .env (mqtt_*, sftp_*, admin и т.п.)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()