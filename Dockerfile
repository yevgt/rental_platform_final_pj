# Используем официальный Python-образ как базовый
FROM python:3.13-slim

SHELL ["/bin/bash", "-c"]

# set enviromment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

RUN pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends \
#    libpq-dev \
#    build-essential \
#    && rm -rf /var/lib/apt/lists/* \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt /app/
# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё содержимое проекта в контейнер
COPY . /app/
# Открываем порт (например, 8000)
EXPOSE 8000

# CMD ["python", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]