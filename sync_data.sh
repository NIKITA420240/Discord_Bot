#!/bin/bash

# Скрипт для синхронизации данных из Docker контейнера

CONTAINER_NAME="discord-bot-v2"
DATA_DIR="./data"

# Создаем директорию для данных если её нет
mkdir -p $DATA_DIR

echo "🔄 Синхронизация данных из контейнера..."

# Копируем файлы из контейнера
if docker exec $CONTAINER_NAME test -f /app/data/bot.log; then
    docker cp $CONTAINER_NAME:/app/data/bot.log $DATA_DIR/
    echo "✅ Логи скопированы"
else
    echo "⚠️ Файл логов не найден в контейнере"
fi

if docker exec $CONTAINER_NAME test -f /app/data/bot_database.db; then
    docker cp $CONTAINER_NAME:/app/data/bot_database.db $DATA_DIR/
    echo "✅ База данных скопирована"
else
    echo "⚠️ Файл базы данных не найден в контейнере"
fi

# Показываем размер файлов
echo "📊 Размер файлов:"
ls -lh $DATA_DIR/

echo "✅ Синхронизация завершена!" 