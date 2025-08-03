#!/bin/bash

echo "🚀 Запуск Discord бота через Docker..."

# Проверяем наличие необходимых файлов
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден! Создайте файл .env с переменными окружения"
    exit 1
fi

if [ ! -f "credentials.json" ]; then
    echo "❌ Файл credentials.json не найден! Добавьте файл с учетными данными Google API"
    exit 1
fi

# Создаем директории если их нет
mkdir -p logs data

# Останавливаем существующий контейнер если он запущен
docker-compose down

# Собираем и запускаем контейнер
echo "📦 Сборка Docker образа..."
docker-compose build

echo "▶️ Запуск бота..."
docker-compose up -d

echo "✅ Бот запущен!"
echo "📋 Просмотр логов: docker-compose logs -f"
echo "🛑 Остановка бота: docker-compose down" 