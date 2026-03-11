import logging
import os
import zipfile
import shutil
import subprocess
import time
import json
import threading

import paramiko
import telebot
from telebot import types

from services.sftp_handler import SFTPClient
from services.mqtt_client import MqttHandler
from config import (
    API_TOKEN,
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


bot = telebot.TeleBot(API_TOKEN)


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_start = types.KeyboardButton('Нажмите, чтобы начать сессию сбора логов')
    markup.add(button_start)
    bot.send_message(
        message.chat.id,
        "Привет, я бот для сбора логов с вашего хаба. Напишите ID вашего хаба и я отправлю вам с него логи.",
        reply_markup=markup,
    )
    user_first_name = message.from_user.first_name or ""
    user_last_name = message.from_user.last_name or ""
    logging.info(f"Пользователь {user_first_name} {user_last_name} (ID: {message.chat.id}) запустил бота.")


@bot.message_handler(func=lambda message: message.text == 'Нажмите, чтобы начать сессию сбора логов')
def handle_button_click(message):
    start(message)


@bot.message_handler(func=lambda message: True)
def handle_hub_id(message):
    global hubID
    user_first_name = message.from_user.first_name or ""
    user_last_name = message.from_user.last_name or ""
    if message.text.lower() == 'speechbot':
        try:
            with open('/root/grekhov/speechbot/bot.log', 'rb') as file_obj:
                bot.send_document(message.chat.id, file_obj)
                logging.info("Файл моих логов успешно отправлен пользователю.")
        except FileNotFoundError:
            bot.send_message(message.chat.id, "Логи не найдены.")
            logging.error("Логи не найдены.")
        except Exception as e:
            bot.send_message(message.chat.id, "Произошла ошибка при отправке логов.")
            logging.error(f"Ошибка: {e}")
        return

    hubID = message.text.strip().lower()
    bot.send_message(message.chat.id, f"ID вашего хаба: {hubID}. Что вы хотите получить?")
    logging.info(f"Получен hubID от пользователя: {hubID}")

    markup = types.InlineKeyboardMarkup()
    button_logs = types.InlineKeyboardButton(text="Все логи", callback_data='get_all_logs')
    button_dump = types.InlineKeyboardButton(text="Дамп выгрузок", callback_data='get_dump')
    button_reboot = types.InlineKeyboardButton(text="Перезагрузить", callback_data='reboot')
    markup.add(button_logs, button_dump, button_reboot)
    bot.send_message(message.chat.id, "Выберите, что вы хотите получить:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ['get_all_logs', 'get_dump', 'reboot'])
def handle_file_options(call):
    if call.data == 'get_all_logs':
        send_logs(call.message)
    elif call.data == 'get_dump':
        send_dump(call.message)
    elif call.data == 'reboot':
        reboot(call.message)


def send_logs(message):
    sftp_client = None
    try:
        mqtt_handler = MqttHandler(
            MQTT_HOST,
            MQTT_PORT,
            MQTT_USERNAME,
            MQTT_PASSWORD,
        )
        while not mqtt_handler.connected:
            time.sleep(0.1)
        mqtt_handler.client.subscribe(f"{hubID}/cmd_response")
        mqtt_handler.publish_command(hubID, "get_logs")
        bot.send_message(message.chat.id, "Собираю логи...")

        response = mqtt_handler.wait_for_response(timeout=10)
        if response is None:
            bot.send_message(
                message.chat.id,
                "Не удалось получить ответ от хаба, вероятно он не онлайн или вне зоны моей видимости :(.",
            )
            logging.error("No response received from the device.")
            mqtt_handler.stop()
            return
        try:
            logging.info(f"Received response: {response}")

            if response.get("status") != 0:
                bot.send_message(
                    message.chat.id,
                    "Ошибка 500. Обратитесь в тех.поддержку по почте helpme@speechmate.ru.",
                )
                logging.error("Received error 500 from the device.")
                return

            bot.send_message(message.chat.id, "Получили ответ от хаба, уже собираю архив :)")
        except json.JSONDecodeError as e:
            bot.send_message(message.chat.id, "Ошибка при получении данных от хаба.")
            logging.error(f"Failed to decode JSON response: {e}")

        mqtt_handler.stop()

        time.sleep(10)

        sftp_client = SFTPClient(
            host=SFTP_HOST,
            port=SFTP_PORT or 22,
            username=SFTP_USER,
            password=SFTP_PASSWORD,
            directory=SFTP_DIRECTORY,
        )
        sftp_client.connect()
        latest_file_name, file_obj = sftp_client.download_latest_archive()

        if file_obj is None:
            bot.send_message(message.chat.id, "Что-то пошло не так... Файлы не найдены на сервере.")
            logging.error("No files found on server.")
            return

        if hubID not in latest_file_name:
            bot.send_message(
                message.chat.id,
                "Что-то пошло не так...Произошла ошибка при сборе логов. Обратитесь в тех.поддержку по почте helpme@speechmate.ru",
            )
            logging.error("No logs found for the specified hub ID.")
            return

        file_obj.seek(0)
        bot.send_document(message.chat.id, (latest_file_name, file_obj))
        file_obj.close()
        logging.info(f"Файл {latest_file_name} успешно отправлен пользователю.")

    except Exception as e:
        bot.send_message(message.chat.id, "Произошла ошибка при сборе логов.")
        logging.error(f"Error in send_logs: {e}")
    finally:
        if sftp_client is not None:
            sftp_client.disconnect()


def send_dump(message):
    sftp_client = None
    try:
        mqtt_handler = MqttHandler(
            MQTT_HOST,
            MQTT_PORT,
            MQTT_USERNAME,
            MQTT_PASSWORD,
        )
        while not mqtt_handler.connected:
            time.sleep(0.1)
        mqtt_handler.client.subscribe(f"{hubID}/cmd_response")
        mqtt_handler.publish_command(hubID, "get_logs")
        bot.send_message(message.chat.id, "Собираю дамп...")

        response = mqtt_handler.wait_for_response(timeout=10)
        if response is None:
            bot.send_message(
                message.chat.id,
                "Не удалось получить ответ от хаба, вероятно он не онлайн или вне зоны моей видимости :(.",
            )
            logging.error("No response received from the device.")
            mqtt_handler.stop()
            return
        else:
            bot.send_message(message.chat.id, "Получили ответ от хаба, уже собираю текстовый файл для вас :)")
            logging.info(f"Received logs: {response}")
        mqtt_handler.stop()
        time.sleep(10)
        sftp_client = SFTPClient(
            host=SFTP_HOST,
            port=SFTP_PORT or 22,
            username=SFTP_USER,
            password=SFTP_PASSWORD,
            directory=SFTP_DIRECTORY,
        )
        sftp_client.connect()
        latest_file_name, file_obj = sftp_client.download_latest_archive()

        if file_obj is None:
            bot.send_message(message.chat.id, "Что-то пошло не так...:( Не найдены файлы на сервере.")
            logging.error("Не найдены файлы на сервере.")
            return
        logging.info(f"Последний файл с сервера: {latest_file_name}")
        if hubID not in latest_file_name:
            bot.send_message(
                message.chat.id,
                "Что-то пошло не так...:( Не найдены логи с указанным ID хаба, убедитесь, что вы ввели корректный ID хаба, и что ваш хаб онлайн.",
            )
            logging.error("Не найдены логи с указанным ID хаба.")
            return

        temp_dir = "/tmp/sftp_logs"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            logging.info(f"Создали директорию для временных файлов: {temp_dir}")

        zip_path = os.path.join(temp_dir, latest_file_name)
        with open(zip_path, 'wb') as f:
            f.write(file_obj.read())
        logging.info(f"Файл {latest_file_name} успешно сохранён в {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            logging.info(f"Файл {latest_file_name} успешно распакован.")
        except Exception as e:
            bot.send_message(message.chat.id, "Ошибка: архив повреждён или неверный формат.")
            logging.error(f"Ошибка при распаковке архива. {e}")
            return

        srs_files = [f for f in os.listdir(temp_dir) if f.startswith('srs')]
        if srs_files:
            logging.info("Файлы srs* найдены. Создаём дамп...")
            dump_file_name = 'upload_dump.txt'
            dump_file_path = os.path.join(temp_dir, dump_file_name)

            try:
                with open(dump_file_path, 'w') as dump_file:
                    for srs_file in srs_files:
                        file_path = os.path.join(temp_dir, srs_file)
                        logging.info(f"Запускаем zgrep для файла: {file_path}")
                        result = subprocess.run(['zgrep', 'Filename', file_path], stdout=dump_file)
                        if result.returncode != 0:
                            logging.warning(f"zgrep не нашёл ничего в файле: {srs_file}")

                if os.path.getsize(dump_file_path) == 0:
                    bot.send_message(message.chat.id, "Дамп не содержит данных.")
                    logging.warning("Файл дампа пуст.")
                    return

            except Exception as e:
                logging.error(f"Ошибка при создании дампа для srs*: {e}")
                bot.send_message(message.chat.id, "Произошла ошибка при создании дампа.")
                return

        else:
            logging.info("Файлы srs* не найдены. Ищем файлы hub*.")
            hub_files = [f for f in os.listdir(temp_dir) if f.startswith('hub')]
            if not hub_files:
                bot.send_message(message.chat.id, "Файлы srs* или hub* не найдены.")
                logging.error("Файлы srs* или hub* не найдены в распакованном архиве.")
                return

            dump_file_name = 'upload_dump.txt'
            dump_file_path = os.path.join(temp_dir, dump_file_name)

            try:
                with open(dump_file_path, 'w') as dump_file:
                    for hub_file in hub_files:
                        file_path = os.path.join(temp_dir, hub_file)
                        logging.info(f"Запускаем zgrep для файла: {file_path}")
                        result = subprocess.run(['zgrep', 'выгружен', file_path], stdout=dump_file)
                        if result.returncode != 0:
                            logging.warning(f"zgrep не нашёл ничего в файле: {hub_file}")

                if os.path.getsize(dump_file_path) == 0:
                    bot.send_message(message.chat.id, "Дамп не содержит данных.")
                    logging.warning("Файл дампа пуст.")
                    return

            except Exception as e:
                logging.error(f"Ошибка при создании дампа для hub*: {e}")
                bot.send_message(message.chat.id, "Произошла ошибка при создании дампа.")
                return
        try:
            with open(dump_file_path, 'rb') as dump_file:
                bot.send_document(message.chat.id, dump_file)
            logging.info(
                f"Файл {dump_file_name} успешно отправлен пользователю {message.from_user.first_name} {message.from_user.last_name}.",
            )
        except Exception as e:
            bot.send_message(message.chat.id, "Произошла ошибка при отправке дампа.")
            logging.error(f"Ошибка при отправке файла: {e}")

        shutil.rmtree(temp_dir)
        logging.info("Временные файлы успешно удалены.")
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла ошибка при сборе дампа.")
        logging.error(f"Error in send_logs: {e}")
    finally:
        if sftp_client is not None:
            sftp_client.disconnect()


def reboot(message):
    try:
        mqtt_handler = MqttHandler(
            MQTT_HOST,
            MQTT_PORT,
            MQTT_USERNAME,
            MQTT_PASSWORD,
        )
        while not mqtt_handler.connected:
            time.sleep(0.1)
        mqtt_handler.client.subscribe(f"{hubID}/cmd_response")
        mqtt_handler.publish_command(hubID, "reboot")
        bot.send_message(message.chat.id, "Отправляю запрос...")

        response = mqtt_handler.wait_for_response(timeout=10)
        if response is None:
            bot.send_message(
                message.chat.id,
                "Не удалось получить ответ от хаба, вероятно он не онлайн или вне зоны моей видимости :(.",
            )
            logging.error("No response received from the device.")
            mqtt_handler.stop()
            return
        else:
            bot.send_message(message.chat.id, "Получили ответ от хаба, уже перезагружаю :)")
            logging.info(f"Received message: {response}")
        mqtt_handler.stop()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла ошибка при попытке перезагрузить.")
        logging.error(f"Error in send_logs: {e}")


def start_bot_polling() -> None:
    logging.info("Запускаем Telegram-бота (polling) в отдельном потоке")
    thread = threading.Thread(target=lambda: bot.polling(none_stop=True), daemon=True)
    thread.start()

