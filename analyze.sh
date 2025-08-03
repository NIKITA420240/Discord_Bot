#!/bin/bash

# Скрипт для анализа базы данных Discord бота

echo "🔍 Анализатор базы данных Discord бота"
echo "======================================"

case "$1" in
    info)
        echo "📊 Информация о базе данных:"
        python3 db_analyzer.py --action info
        ;;
    recent)
        limit=${2:-10}
        echo "📋 Последние записи (лимит: $limit):"
        python3 db_analyzer.py --action recent --limit $limit
        ;;
    stats)
        days=${2:-7}
        echo "🏆 Статистика за $days дней:"
        python3 db_analyzer.py --action stats --days $days
        ;;
    curator)
        if [ -z "$2" ]; then
            echo "❌ Укажите имя куратора"
            echo "Пример: $0 curator 'Самойлов Никита'"
            exit 1
        fi
        days=${3:-7}
        echo "👤 Статистика куратора '$2' за $days дней:"
        python3 db_analyzer.py --action curator --curator "$2" --days $days
        ;;
    daily)
        date=${2:-$(date +%Y-%m-%d)}
        echo "📅 Сводка за $date:"
        python3 db_analyzer.py --action daily --date $date
        ;;
    export-csv)
        filename=${2:-""}
        if [ -n "$filename" ]; then
            echo "📤 Экспорт в CSV: $filename"
            python3 db_analyzer.py --action export-csv --output "$filename"
        else
            echo "📤 Экспорт в CSV (автоимя):"
            python3 db_analyzer.py --action export-csv
        fi
        ;;
    export-json)
        filename=${2:-""}
        if [ -n "$filename" ]; then
            echo "📤 Экспорт в JSON: $filename"
            python3 db_analyzer.py --action export-json --output "$filename"
        else
            echo "📤 Экспорт в JSON (автоимя):"
            python3 db_analyzer.py --action export-json
        fi
        ;;
    *)
        echo "Использование: $0 {info|recent|stats|curator|daily|export-csv|export-json}"
        echo ""
        echo "Команды:"
        echo "  info                    - Общая информация о БД"
        echo "  recent [лимит]          - Последние записи (по умолчанию 10)"
        echo "  stats [дни]             - Топ кураторов (по умолчанию 7 дней)"
        echo "  curator имя [дни]       - Статистика конкретного куратора"
        echo "  daily [дата]            - Сводка за день (YYYY-MM-DD)"
        echo "  export-csv [файл]       - Экспорт в CSV"
        echo "  export-json [файл]      - Экспорт в JSON"
        echo ""
        echo "Примеры:"
        echo "  $0 info"
        echo "  $0 recent 5"
        echo "  $0 stats 30"
        echo "  $0 curator 'Самойлов Никита' 7"
        echo "  $0 daily 2025-08-03"
        echo "  $0 export-csv my_data.csv"
        exit 1
        ;;
esac 