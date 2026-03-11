import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

# Создаем папку logs если её нет
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
SERVICES_LOGS_DIR = LOGS_DIR / "services"
SERVICES_LOGS_DIR.mkdir(exist_ok=True)

# Базовый формат логов
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str, log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Настройка логгера для конкретного сервиса

    Args:
        name: Имя логгера (обычно __name__)
        log_file: Имя файла лога (если не указано, используется имя сервиса)
        level: Уровень логирования

    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)

    # Избегаем дублирования обработчиков
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Определяем имя файла лога
    if log_file is None:
        # Извлекаем имя сервиса из полного пути модуля
        service_name = name.split('.')[-1] if '.' in name else name
        log_file = f"{service_name}.log"

    # Путь к файлу лога
    log_path = SERVICES_LOGS_DIR / log_file

    # Создаем обработчик для файла с ротацией
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)

    # Создаем форматтер
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(formatter)

    # Добавляем обработчик к логгеру
    logger.addHandler(file_handler)

    # Также добавляем консольный вывод для разработки
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_service_logger(service_name: str) -> logging.Logger:
    """
    Получить логгер для конкретного сервиса

    Args:
        service_name: Имя сервиса (например, 'bot_service', 'media_service')

    Returns:
        Настроенный логгер для сервиса
    """
    return setup_logger(f"services.{service_name}", f"{service_name}.log")


def get_api_logger(api_name: str) -> logging.Logger:
    """
    Получить логгер для API endpoint

    Args:
        api_name: Имя API (например, 'users', 'matches')

    Returns:
        Настроенный логгер для API
    """
    return setup_logger(f"api.{api_name}", f"api_{api_name}.log")


def get_crud_logger(crud_name: str) -> logging.Logger:
    """
    Получить логгер для CRUD операций

    Args:
        crud_name: Имя CRUD (например, 'users_crud', 'matches_crud')

    Returns:
        Настроенный логгер для CRUD
    """
    return setup_logger(f"crud.{crud_name}", f"crud_{crud_name}.log")


# Основной логгер приложения
main_logger = setup_logger("support_bot_backend", "main.log")

# Логгер для ошибок
error_logger = setup_logger("errors", "errors.log", logging.ERROR)

# Логгер для базы данных
db_logger = setup_logger("database", "database.log")

# Логгер для веб-сокетов
websocket_logger = setup_logger("websocket", "websocket.log")

# Логгер для аутентификации
auth_logger = setup_logger("auth", "auth.log")

# Логгер для платежей
payment_logger = setup_logger("payments", "payments.log")


def log_service_call(service_name: str, method_name: str, **kwargs):
    """
    функция для логирования вызовов сервисов

    Args:
        service_name: Имя сервиса
        method_name: Имя метода
        **kwargs: Дополнительные параметры для логирования
    """
    logger = get_service_logger(service_name)
    params = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"Calling {method_name}({params})")


def log_error(service_name: str, error: Exception, context: str = ""):
    """
    функция для логирования ошибок

    Args:
        service_name: Имя сервиса
        error: Объект исключения
        context: Дополнительный контекст
    """
    logger = get_service_logger(service_name)
    error_logger.error(f"Error in {service_name}: {str(error)} - Context: {context}")
    logger.error(f"Error: {str(error)} - Context: {context}")


# Инициализация основных логгеров
main_logger.info("Logging system initialized")
main_logger.info(f"Logs directory: {LOGS_DIR.absolute()}")
main_logger.info(f"Services logs directory: {SERVICES_LOGS_DIR.absolute()}")