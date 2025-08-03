#!/bin/bash

# Скрипт для управления Discord ботом

case "$1" in
    start)
        echo "🚀 Запуск бота..."
        docker-compose up -d
        echo "✅ Бот запущен!"
        ;;
    stop)
        echo "🛑 Остановка бота..."
        docker-compose down
        echo "✅ Бот остановлен!"
        ;;
    restart)
        echo "🔄 Перезапуск бота..."
        docker-compose restart
        echo "✅ Бот перезапущен!"
        ;;
    logs)
        echo "📋 Просмотр логов..."
        docker-compose logs -f
        ;;
    status)
        echo "📊 Статус бота:"
        docker-compose ps
        echo ""
        echo "📁 Размер файлов данных:"
        ls -lh bot.log bot_database.db 2>/dev/null || echo "Файлы данных не найдены"
        ;;
    backup)
        echo "💾 Создание резервной копии..."
        mkdir -p backups
        cp bot.log "backups/bot_$(date +%Y%m%d_%H%M%S).log"
        cp bot_database.db "backups/bot_database_$(date +%Y%m%d_%H%M%S).db"
        echo "✅ Резервная копия создана в папке backups/"
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|logs|status|backup}"
        echo ""
        echo "Команды:"
        echo "  start   - Запустить бота"
        echo "  stop    - Остановить бота"
        echo "  restart - Перезапустить бота"
        echo "  logs    - Показать логи в реальном времени"
        echo "  status  - Показать статус и размер файлов"
        echo "  backup  - Создать резервную копию данных"
        exit 1
        ;;
esac 