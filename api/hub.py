from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Tuple
import io
import os
import zipfile
import shutil
import subprocess
import logging
import time

from services.mqtt_client import MqttHandler
from services.sftp_handler import SFTPClient
from services.bot import bot
from utils.dependencies import get_current_user
from models import models
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


router = APIRouter()


def _request_logs_from_hub(hub_id: str, command: str) -> dict:
    mqtt_handler = MqttHandler(
        MQTT_HOST,
        MQTT_PORT,
        MQTT_USERNAME,
        MQTT_PASSWORD,
    )
    while not mqtt_handler.connected:
        time.sleep(0.1)

    mqtt_handler.client.subscribe(f"{hub_id}/cmd_response")
    mqtt_handler.publish_command(hub_id, command)

    response = mqtt_handler.wait_for_response(timeout=10)
    mqtt_handler.stop()

    if response is None:
        logging.error("No response received from the device.")
        raise HTTPException(
            status_code=504,
            detail="Не удалось получить ответ от хаба, вероятно он не онлайн или вне зоны видимости.",
        )

    if response.get("status") != 0:
        logging.error("Received non-zero status from device response.")
        raise HTTPException(
            status_code=500,
            detail="Ошибка на стороне устройства. Обратитесь в техподдержку.",
        )

    return response


def _download_latest_archive_for_hub(hub_id: str) -> Tuple[str, io.BytesIO]:
    sftp_client = SFTPClient(
        host=SFTP_HOST,
        port=SFTP_PORT or 22,
        username=SFTP_USER,
        password=SFTP_PASSWORD,
        directory=SFTP_DIRECTORY,
    )
    try:
        sftp_client.connect()
        latest_file_name, file_obj = sftp_client.download_latest_archive()
        if file_obj is None:
            logging.error("No files found on server.")
            raise HTTPException(
                status_code=404,
                detail="Файлы не найдены на сервере.",
            )
        if hub_id not in latest_file_name:
            logging.error("No logs found for the specified hub ID.")
            raise HTTPException(
                status_code=404,
                detail="Не найдены логи с указанным ID хаба.",
            )
        file_obj.seek(0)
        return latest_file_name, file_obj
    finally:
        sftp_client.disconnect()


@router.post("/hub/{hub_id}/logs")
def get_hub_logs(
    hub_id: str,
    current_user: models.User = Depends(get_current_user),
):
    _request_logs_from_hub(hub_id, "get_logs")
    time.sleep(10)

    filename, file_obj = _download_latest_archive_for_hub(hub_id)

    # Отправляем архив пользователю в Telegram по его telegram_id
    data = file_obj.getvalue()
    tg_file = io.BytesIO(data)
    tg_file.name = filename
    bot.send_document(current_user.telegram_id, tg_file)
    file_obj = io.BytesIO(data)

    return StreamingResponse(
        file_obj,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/hub/{hub_id}/dump")
def get_hub_dump(
    hub_id: str,
    current_user: models.User = Depends(get_current_user),
):
    _request_logs_from_hub(hub_id, "get_logs")
    time.sleep(10)

    filename, file_obj = _download_latest_archive_for_hub(hub_id)

    temp_dir = "/tmp/sftp_logs"
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = os.path.join(temp_dir, filename)
    with open(zip_path, "wb") as f:
        f.write(file_obj.read())

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail="Ошибка: архив повреждён или неверный формат.",
        )

    srs_files = [f for f in os.listdir(temp_dir) if f.startswith("srs")]
    hub_files = [f for f in os.listdir(temp_dir) if f.startswith("hub")] if not srs_files else []

    if not srs_files and not hub_files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=404,
            detail="Файлы srs* или hub* не найдены.",
        )

    dump_file_name = "upload_dump.txt"
    dump_file_path = os.path.join(temp_dir, dump_file_name)

    try:
        with open(dump_file_path, "w", encoding="utf-8") as dump_file:
            if srs_files:
                for srs_file in srs_files:
                    file_path = os.path.join(temp_dir, srs_file)
                    subprocess.run(["zgrep", "Filename", file_path], stdout=dump_file, check=False)
            else:
                for hub_file in hub_files:
                    file_path = os.path.join(temp_dir, hub_file)
                    subprocess.run(["zgrep", "выгружен", file_path], stdout=dump_file, check=False)

        if os.path.getsize(dump_file_path) == 0:
            raise HTTPException(
                status_code=404,
                detail="Дамп не содержит данных.",
            )

        with open(dump_file_path, "rb") as dump_file:
            data = dump_file.read()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Отправляем дамп пользователю в Telegram по его telegram_id
    tg_file = io.BytesIO(data)
    tg_file.name = dump_file_name
    bot.send_document(current_user.telegram_id, tg_file)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{dump_file_name}"'},
    )


@router.post("/hub/{hub_id}/reboot")
def reboot_hub(hub_id: str):
    mqtt_handler = MqttHandler(
        MQTT_HOST,
        MQTT_PORT,
        MQTT_USERNAME,
        MQTT_PASSWORD,
    )
    try:
        while not mqtt_handler.connected:
            time.sleep(0.1)
        mqtt_handler.client.subscribe(f"{hub_id}/cmd_response")
        mqtt_handler.publish_command(hub_id, "reboot")

        response = mqtt_handler.wait_for_response(timeout=10)
        if response is None:
            logging.error("No response received from the device.")
            raise HTTPException(
                status_code=504,
                detail="Не удалось получить ответ от хаба, вероятно он не онлайн или вне зоны видимости.",
            )

        return {"status": "ok", "response": response}
    finally:
        mqtt_handler.stop()

