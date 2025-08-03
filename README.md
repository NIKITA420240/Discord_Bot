# Discord Bot для сбора статистики кураторов

Этот бот автоматически собирает статистику работы кураторов в Discord канале и обновляет Google Sheets таблицу.

## Функциональность

- Автоматический сбор сообщений кураторов за каждый час
- Парсинг количества чатов из сообщений
- Обновление Google Sheets таблицы
- Команды для ручного обновления и просмотра данных
- Автоматические напоминания кураторам

## Установка и настройка

### Требования
- Python 3.11+
- Discord Bot Token
- Google Sheets API credentials

### Переменные окружения
Создайте файл `.env` со следующими переменными:
```
DISCORD_TOKEN=your_discord_bot_token
SPREADSHEET_ID=your_google_sheets_id
GUILD_ID=your_discord_server_id
CHANNEL_ID=your_discord_channel_id
```

### Установка зависимостей
```bash
pip install -r requirements.txt
```

### Запуск
```bash
python bot.py
```

## Docker

Для запуска в Docker:
```bash
docker build -t discord-bot .
docker run -d --env-file .env discord-bot
```

## Команды бота

- `!обнови` - Принудительное обновление данных в таблице
- `!покажи` - Показать последние собранные данные

## Структура проекта

- `bot.py` - Основной файл бота
- `collect.py` - Логика сбора данных из Discord
- `sheets.py` - Работа с Google Sheets
- `users.py` - Маппинг пользователей Discord на имена кураторов
- `utils.py` - Константы и утилиты
- `requirements.txt` - Зависимости Python
- `Dockerfile` - Конфигурация Docker

## Логирование

Бот ведет подробные логи в файле `bot.log` с временными метками по московскому времени. 