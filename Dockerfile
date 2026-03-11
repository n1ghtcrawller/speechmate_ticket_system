# Используем зеркало Alpine репозитория для ускорения
FROM python:3.11-alpine

# Настраиваем зеркало Alpine репозитория
RUN echo "https://mirror.yandex.ru/mirrors/alpine/v3.22/main" > /etc/apk/repositories && \
    echo "https://mirror.yandex.ru/mirrors/alpine/v3.22/community" >> /etc/apk/repositories

# Устанавливаем FFmpeg и bash из зеркала
RUN apk update && apk add --no-cache \
    bash \
    && rm -rf /var/cache/apk/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только requirements.txt для кэширования зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем только необходимые файлы приложения
COPY . .

# Экспонируем порт
EXPOSE 8080

# Запускаем приложение с оптимизациями для production
# Используем 1 worker на ядро CPU (можно настроить через переменную окружения)
# --workers 0 означает использовать количество CPU ядер
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--loop", "uvloop", "--no-access-log"]