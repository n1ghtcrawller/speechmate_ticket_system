import asyncio
import logging

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from middleware.logging import log_requests
from fastapi.middleware.cors import CORSMiddleware
from database import Base, async_engine, init_db
from api import auth, users, hub, support
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from services.bot import start_bot_polling
from services.sftp_handler import SFTPClient
from services.mqtt_client import MqttHandler
from config import (
    SFTP_HOST,
    SFTP_PORT,
    SFTP_USER,
    SFTP_PASSWORD,
    SFTP_DIRECTORY,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
)

app = FastAPI(title="Telegram Task Tracker")


# Middleware для оптимизации кэширования статических файлов
class StaticCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Заголовки кэширования для статических файлов
        if request.url.path.startswith("/media/static/"):
            # Определяем тип файла и устанавливаем соответствующие заголовки кэширования
            if request.url.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                response.headers["Cache-Control"] = "public, max-age=86400"  # 24 часа для изображений
            elif request.url.path.endswith(('.mp4', '.avi', '.mov', '.webm')):
                response.headers["Cache-Control"] = "public, max-age=3600"  # 1 час для видео
            else:
                response.headers["Cache-Control"] = "public, max-age=1800"  # 30 минут для остальных файлов

            # ETag для лучшего кэширования
            if hasattr(response, 'headers') and 'etag' not in response.headers:
                import hashlib
                import time
                etag = hashlib.md5(f"{request.url.path}{time.time()}".encode()).hexdigest()
                response.headers["ETag"] = f'"{etag}"'

        return response


# Логирование всех запросов
app.middleware("http")(log_requests)

# Middleware для кэширования статических файлов
app.add_middleware(StaticCacheMiddleware)

# кроссдоменые запросы cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def check_sftp_connection():
    try:
        client = SFTPClient(
            host=SFTP_HOST,
            port=SFTP_PORT or 22,
            username=SFTP_USER,
            password=SFTP_PASSWORD,
            directory=SFTP_DIRECTORY,
        )
        client.connect()
        client.disconnect()
        logging.info("SFTP: подключение успешно.")
    except Exception as e:
        logging.error(f"SFTP: не удалось подключиться ({e}).")


async def check_mqtt_connection():
    try:
        handler = MqttHandler(
            MQTT_HOST,
            MQTT_PORT,
            MQTT_USERNAME,
            MQTT_PASSWORD,
        )
        # ждём подключения ограниченное время
        for _ in range(50):  # ~5 секунд
            if handler.connected:
                break
            await asyncio.sleep(0.1)

        if handler.connected:
            logging.info("MQTT: подключение успешно.")
        else:
            logging.error("MQTT: не удалось подключиться (таймаут).")
        handler.stop()
    except Exception as e:
        logging.error(f"MQTT: не удалось подключиться ({e}).")


@app.on_event("startup")
async def on_startup():
    await init_db()
    # Проверяем внешние сервисы
    await check_sftp_connection()
    await check_mqtt_connection()
    # Запускаем Telegram-бота
    start_bot_polling()
    print("FastAPI приложение запущено. Telegram-бот запущен в фоне.")


# статические файлы для медиа
# с оптимизированными настройками кэширования
app.mount("/media/static", StaticFiles(
    directory="uploads",
    html=True,  #  обслуживание HTML файлов
    check_dir=True  # существование директории
), name="static_media")

@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    return Response(status_code=200)


@app.get("/")
def root():
    return {"API": "Working"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(hub.router, prefix="/hub-api", tags=["hub"])
app.include_router(support.router, prefix="/support", tags=["support"])