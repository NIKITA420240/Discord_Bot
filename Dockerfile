# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . .

# (Опционально) Установить зависимости, если есть requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Запуск основного скрипта (замените на нужный)
CMD ["python", "bot.py"]