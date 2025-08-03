# Discord Bot v2 - Система учета кураторов

Полнофункциональный Discord бот для автоматического сбора и анализа статистики кураторов с интеграцией SQLite базы данных, Google Sheets и Docker-контейнеризацией.

## 🚀 Возможности

### 🤖 Автоматизация
- **Автоматический сбор данных** каждый час (8:00-23:00)
- **Интеграция с Google Sheets** - автоматическое обновление таблиц
- **Создание новых листов** - копирование шаблона для каждого дня
- **Умная обработка** - исключение дубликатов и проверка данных

### 📊 База данных SQLite
- **Автоматическое сохранение** всех сообщений кураторов
- **История сообщений** с возможностью детального анализа
- **Статистика по периодам** (день, неделя, месяц)
- **Топ кураторов** за любой период
- **Очистка старых данных** для оптимизации

### 🔍 Аналитика и экспорт
- **Встроенный анализатор БД** - Python скрипт для работы с данными
- **Экспорт в CSV/JSON** - для дальнейшего анализа
- **Детальная статистика** - по кураторам, дням, часам
- **Визуализация данных** - удобные отчеты и сводки

## 📋 Команды бота

### Основные команды
- `!обнови` - Принудительное обновление данных и Google Sheets
- `!покажи` - Показать последние собранные данные
- `!проверить` - Проверить последнее сообщение в канале

### Аналитические команды
- `!статистика` - Показать общую статистику базы данных
- `!топ [дни]` - Топ кураторов за период (по умолчанию 7 дней)
- `!история [куратор] [дни]` - История конкретного куратора
- `!очистить [дни]` - Удалить старые записи (по умолчанию 90 дней)

## 🐳 Установка и запуск с Docker

### Быстрый старт
```bash
# Клонировать репозиторий
git clone <repository-url>
cd Bot-v2

# Создать файлы конфигурации
cp .env.example .env
# Отредактировать .env с вашими данными

# Добавить credentials.json для Google Sheets API

# Запустить бота
./run.sh
```

### Ручной запуск
```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### Управление ботом
```bash
# Использовать удобный скрипт управления
./manage.sh start      # Запуск
./manage.sh stop       # Остановка
./manage.sh restart    # Перезапуск
./manage.sh status     # Статус
./manage.sh logs       # Логи
./manage.sh backup     # Резервная копия
```

## ⚙️ Конфигурация

### Переменные окружения (.env)
```env
DISCORD_TOKEN=your_discord_bot_token
SPREADSHEET_ID=your_google_sheets_id
GUILD_ID=your_discord_server_id
CHANNEL_ID=your_discord_channel_id
```

### Google Sheets API
1. Создайте проект в Google Cloud Console
2. Включите Google Sheets API
3. Создайте Service Account
4. Скачайте `credentials.json`
5. Добавьте Service Account в вашу Google таблицу

### Структура Google Sheets
- **Шаблонный лист** "Шаблон" с заголовками
- **Автоматическое создание** листов для каждого дня
- **Формат листов**: "18 июня", "3 августа" и т.д.

## 📊 Анализ данных

### Встроенный анализатор
```bash
# Общая информация о БД
./analyze.sh info

# Последние записи
./analyze.sh recent 10

# Топ кураторов
./analyze.sh stats 30

# Статистика конкретного куратора
./analyze.sh curator "Имя Фамилия" 7

# Сводка за день
./analyze.sh daily 2025-08-03

# Экспорт данных
./analyze.sh export-csv report.csv
./analyze.sh export-json data.json
```

### Python API
```python
from db_analyzer import DatabaseAnalyzer

analyzer = DatabaseAnalyzer("bot_database.db")

# Получить статистику
info = analyzer.get_database_info()

# Экспортировать данные
analyzer.export_to_csv("report.csv")
```

## 🗄️ Структура базы данных

```sql
CREATE TABLE curator_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curator_name TEXT NOT NULL,
    discord_id TEXT NOT NULL,
    message_date DATE NOT NULL,
    message_hour INTEGER NOT NULL,
    chats_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(curator_name, message_date, message_hour)
);
```

## 📁 Структура проекта

```
Bot-v2/
├── bot.py                 # Основной файл бота
├── database.py            # Управление SQLite БД
├── collect.py             # Сбор данных
├── sheets.py              # Google Sheets интеграция
├── users.py               # Маппинг пользователей
├── utils.py               # Константы и утилиты
├── db_analyzer.py         # Анализатор базы данных
├── requirements.txt       # Python зависимости
├── Dockerfile             # Docker образ
├── docker-compose.yml     # Docker Compose конфигурация
├── .env                   # Переменные окружения
├── credentials.json       # Google API ключи
├── manage.sh              # Скрипт управления ботом
├── analyze.sh             # Скрипт анализа данных
├── run.sh                 # Скрипт быстрого запуска
├── bot.log                # Логи бота
└── bot_database.db        # SQLite база данных
```

## 🔧 Архитектура

### Модули
- **`bot.py`** - Основной файл бота с командами и логикой
- **`database.py`** - Управление SQLite базой данных
- **`collect.py`** - Сбор данных с интеграцией БД
- **`sheets.py`** - Работа с Google Sheets API
- **`users.py`** - Маппинг Discord ID на имена кураторов
- **`utils.py`** - Константы и вспомогательные функции
- **`db_analyzer.py`** - Анализатор и экспорт данных

### Docker контейнеры
- **Python 3.11** - основная среда выполнения
- **Автоматический перезапуск** - при сбоях
- **Монтирование файлов** - логи и БД сохраняются на хосте
- **Изоляция** - безопасное выполнение

## 📈 Мониторинг и логирование

### Логи
- **Файл логов**: `bot.log`
- **Формат**: `2025-08-03 23:56:37 [INFO] Сообщение`
- **Временная зона**: Москва (UTC+3)
- **Уровни**: INFO, WARNING, ERROR

### Мониторинг
```bash
# Просмотр логов в реальном времени
tail -f bot.log

# Статус бота
./manage.sh status

# Размер файлов данных
ls -lh bot.log bot_database.db
```

## 🔄 Обслуживание

### Резервное копирование
```bash
# Автоматическое резервное копирование
./manage.sh backup

# Ручное копирование
cp bot_database.db backups/backup_$(date +%Y%m%d_%H%M%S).db
```

### Очистка данных
```bash
# Через команду бота
!очистить 90

# Через анализатор
python3 db_analyzer.py --action cleanup --days 90
```

### Обновление
```bash
# Остановить бота
./manage.sh stop

# Обновить код
git pull

# Пересобрать и запустить
docker-compose build
./manage.sh start
```

## 🛠️ Разработка

### Локальная разработка
```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить бота локально
python bot.py

# Запустить анализатор
python db_analyzer.py --action info
```

### Тестирование
```bash
# Проверить подключение к БД
python3 db_analyzer.py --action info

# Протестировать экспорт
python3 db_analyzer.py --action export-csv test.csv
```

## 📝 Лицензия

MIT License - свободное использование и модификация.

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте логи: `tail -f bot.log`
2. Проверьте статус: `./manage.sh status`
3. Перезапустите бота: `./manage.sh restart`
4. Создайте issue в репозитории

## 🚀 Roadmap

- [ ] Веб-интерфейс для анализа данных
- [ ] Интеграция с другими мессенджерами
- [ ] Расширенная аналитика и графики
- [ ] API для внешних систем
- [ ] Система уведомлений
- [ ] Автоматические отчеты 