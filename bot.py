from google.oauth2.service_account import Credentials
import gspread
from operator import truediv
import os
import asyncio
from functools import partial
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from utils import (
    CHECK_MINUTES, 
    LOG_CHANNEL_ID, 
    SCOPES, 
    CREDENTIALS_FILE
)
from users import get_tag_by_name # Импортируем функцию для тегов
import sys
import matplotlib.pyplot as plt

from collect import DataCollector
from database import DatabaseManager
from sheets import update_both_tables, get_scheduled_workers, get_senior_for_hour # Импортируем новую функцию

# Логирование
class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc) + timedelta(hours=3) # +3 часа для Москвы
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime("%Y-%m-%d %H:%M:%S")

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Очищаем существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Обработчик для файла
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_formatter = MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_formatter = MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Загрузка переменных
load_dotenv()

def get_env_var(name, required=True) -> str:
    value = os.getenv(name)
    if required and value is None:
        logging.error(f"Не найдена переменная окружения: {name}. Завершаем работу.")
        sys.exit(1)
    return str(value)

TOKEN = get_env_var("DISCORD_TOKEN")
SPREADSHEET_ID = get_env_var("SPREADSHEET_ID")
SPREADSHEET_ID_SCHEDULE = get_env_var("SPREADSHEET_ID_SCHEDULE")
GUILD_ID = int(get_env_var("GUILD_ID"))
CHANNEL_ID = int(get_env_var("CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0)) # Загружаем ID канала из .env

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Переменная для хранения времени последнего отправления
last_sent = None

# Логируем после инициализации
logging.info("Discord бот инициализирован")
logging.info("База данных подключена")

async def update_sheet(force_schedule_update=False):
    """
    Обновляет Google Sheets и базу данных (Асинхронно).
    force_schedule_update: Если True, то принудительно обновит таблицу "Рабочие часы" (имена).
                           Если False, обновит только статистику (цифры), чтобы не мусорить в истории.
    """
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        logging.error("Сервер не найден!")
        return {}, 0, 0, "", False
        
    channel = guild.get_channel(CHANNEL_ID)
    if not channel:
        logging.error("Канал не найден")
        return {}, 0, 0, "", False

    # Сбор данных
    result = await data_collector.collect_discord_data(channel)
    
    # Распаковка результатов (5 элементов)
    curator_data = result[0]
    hour = result[1]
    day = result[2]
    month_name = result[3]
    dt_obj = result[4] # Объект даты для правильного поиска недели

    # Обновляем Google Sheets (В ОТДЕЛЬНОМ ПОТОКЕ)
    if curator_data:
        loop = asyncio.get_running_loop()
        
        success = await loop.run_in_executor(
            None, 
            partial(
                update_both_tables, 
                SPREADSHEET_ID,          # ID таблицы статистики
                SPREADSHEET_ID_SCHEDULE, # ID таблицы расписания (имен)
                curator_data, 
                hour, 
                day, 
                month_name, 
                dt_obj,
                force_schedule_update    # <-- Передаем флаг: нужно ли обновлять имена сейчас?
            )
        )
        return curator_data, hour, day, month_name, success
    else:
        logging.info("Нет данных для обновления")
        return {}, hour, day, month_name, True

async def read_channel_message(channel):
    """Читает одно сообщение из канала и проверяет, является ли оно сообщением бота"""
    try:
        # Получаем последнее сообщение из канала
        async for message in channel.history(limit=1):
            if message.author.bot:
                # Сообщение отправлено ботом
                logging.info(f"Получено сообщение от бота: {message.content}")
                return message, True  # True = сообщение от бота
            else:
                # Сообщение отправлено пользователем
                logging.info(f"Получено сообщение от пользователя {message.author}: {message.content}")
                return message, False  # False = сообщение от пользователя
        # Если нет сообщений в истории
        return None, None
    except Exception as e:
        logging.error(f"Ошибка при чтении сообщения из канала: {e}")
        return None, None

async def last_message_check_is_not_chats(channel):
    """Проверяет, не является ли последнее сообщение в канале сообщением о количестве чатов"""
    result = await read_channel_message(channel)
    if result[0] is None:
        return None
    
    message, is_bot = result
    if is_bot and message.content.startswith("Пишите количество чатов за"):
        return False
    else:
        return True


# Команда "!обнови"
@bot.command(name="обнови")
@commands.has_any_role("Старший куратор", "Admin", "Administrator")
async def обнови(ctx):
    await ctx.send("🔄 Собираю данные и принудительно обновляю ОБЕ таблицы (Статистику и Расписание)...")
    
    # force_schedule_update=True -> Запишет и цифры, и имена кураторов
    curator_data, hour, day, month_name, success = await update_sheet(force_schedule_update=True)
    
    status = "успешно" if success else "с ошибками"
    await ctx.send(f"✅ Готово! Статус: {status}. Обработано: {len(curator_data)} записей за {day} {month_name}, {hour}:00 часов.")

# Команда "!покажи"
@bot.command(name="покажи")
async def покажи(ctx):
    try:
        curator_data, hour, day, month_name, message_date = await data_collector.collect_discord_data(
            bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        )
        
        if not curator_data:
            await ctx.send("Нет данных за последний час.")
            return
            
        message = "**Последние данные:**\n"
        for name, count in curator_data.items():
            message += f"- {name} [{day} {month_name}] [{hour}:00]: {count} чатов\n"
            
        await ctx.send(message)
    except Exception as e:
        logging.error(f"Ошибка в команде покажи: {e}")
        await ctx.send("Произошла ошибка при получении данных")

# Команда "!статистика"
@bot.command(name="статистика")
async def статистика(ctx):
    """Показывает статистику базы данных"""
    try:
        stats = db_manager.get_database_stats()
        if stats:
            message = "**📊 Статистика базы данных:**\n"
            message += f"📝 Всего записей: {stats['total_records']}\n"
            message += f"👥 Уникальных кураторов: {stats['unique_curators']}\n"
            message += f"📅 Первая запись: {stats['oldest_date']}\n"
            message += f"📅 Последняя запись: {stats['newest_date']}\n"
        else:
            message = "База данных пуста или произошла ошибка при получении статистики."
        
        await ctx.send(message)
    except Exception as e:
        logging.error(f"Ошибка в команде статистика: {e}")
        await ctx.send("Произошла ошибка при получении статистики")

# Команда "!топ по количеству чатов"
@bot.command(name="топдетей")
async def топ(ctx, days: int = 7):
    """Показывает топ кураторов за указанное количество дней"""
    try:
        if days > 30:
            await ctx.send("Максимальный период - 30 дней.")
            return
            
        top_curators = data_collector.get_top_curators_count_sms(days, 10)
        if top_curators:
            message = f"**🏆 Топ кураторов за {days} дней:**\n"
            for i, (name, count) in enumerate(top_curators, 1):
                message += f"{i}. {name}: {count} чатов\n"
        else:
            message = f"Нет данных за последние {days} дней."
        
        await ctx.send(message)
    except Exception as e:
        logging.error(f"Ошибка в команде топ: {e}")
        await ctx.send("Произошла ошибка при получении топ кураторов")

# Команда "!топ"
@bot.command(name="топ")
async def топ(ctx, days: int = 7):
    """Показывает топ кураторов за указанное количество дней"""
    try:
        if days > 30:
            await ctx.send("Максимальный период - 30 дней.")
            return
            
        top_curators = data_collector.get_top_curators_count_hours(days, 10)
        if top_curators:
            message = f"**🏆 Топ кураторов за {days} дней:**\n"
            for i, (name, count) in enumerate(top_curators, 1):
                message += f"{i}. {name}: {count} часов\n"
        else:
            message = f"Нет данных за последние {days} дней."
        
        await ctx.send(message)
    except Exception as e:
        logging.error(f"Ошибка в команде топ: {e}")
        await ctx.send("Произошла ошибка при получении топ кураторов")

# Команда "!история"
@bot.command(name="история")
async def история(ctx, *curator_name: str, days: int = 7):
    """Показывает историю куратора за указанное количество дней"""
    try:
        if days > 30:
            await ctx.send("Максимальный период - 30 дней.")
            return
        curator_name = ' '.join(curator_name)
        history = data_collector.get_curator_history(curator_name, days)
        if history:
            message = f"**📈 История {curator_name} за {days} дней:**\n"
            for date, hour, count, created_at in history[:10]:  # Показываем только последние 10 записей
                message += f"- {date} {hour}:00: {count} чатов\n"
        else:
            message = f"Нет данных для {curator_name} за последние {days} дней."
        
        await ctx.send(message)
    except Exception as e:
        logging.error(f"Ошибка в команде история: {e}")
        await ctx.send("Произошла ошибка при получении истории")

# Команда "!очистить"
@bot.command(name="очистить")
@commands.has_any_role("старший куратор", "Admin", "Administrator")
async def очистить(ctx, days: int = 90):
    """Удаляет старые записи из базы данных"""
    try:
        if days < 30:
            await ctx.send("Минимальный период для очистки - 30 дней.")
            return
            
        deleted_count = db_manager.delete_old_records(days)
        await ctx.send(f"Удалено {deleted_count} записей старше {days} дней.")
    except Exception as e:
        logging.error(f"Ошибка в команде очистить: {e}")
        await ctx.send("Произошла ошибка при очистке базы данных")

# Команда "!последние"
@bot.command(name="последние")
async def последние(ctx, k: int = 10):
    """Показывает последние k сообщений из базы данных (по умолчанию 10)"""
    try:
        if k <= 0:
            await ctx.send("Количество сообщений должно быть больше 0.")
            return
        
        if k > 50:
            await ctx.send("Максимальное количество сообщений для вывода - 50.")
            return
            
        messages = db_manager.get_last_k_messages(k)
        
        if not messages:
            await ctx.send("В базе данных нет сообщений.")
            return
        
        # Формируем красивый вывод
        response = f"📋 **Последние {len(messages)} сообщений из базы данных:**\n\n"
        
        for i, (curator_name, discord_id, message_date, message_hour, chats_count, created_at) in enumerate(messages, 1):
            # Форматируем дату создания записи
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_formatted = created_dt.strftime("%d.%m.%Y %H:%M:%S")
            except:
                created_formatted = created_at
            
            response += f"`{i:2d}.` **{curator_name}** | {message_date} {message_hour:02d}:00 | {chats_count} чатов \n"
        
        # Discord имеет ограничение на длину сообщения (2000 символов)
        if len(response) > 1900:
            # Разбиваем на части
            parts = []
            current_part = f"📋 **Последние {len(messages)} сообщений из базы данных:**\n\n"
            
            for i, (curator_name, discord_id, message_date, message_hour, chats_count, created_at) in enumerate(messages, 1):
                try:
                    created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_formatted = created_dt.strftime("%d.%m.%Y %H:%M:%S")
                except:
                    created_formatted = created_at
                
                line = f"`{i:2d}.` **{curator_name}** | {message_date} {message_hour:02d}:00 | {chats_count} чатов \n"
                
                if len(current_part + line) > 1900:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += line
            
            if current_part:
                parts.append(current_part)
            
            # Отправляем по частям
            for part in parts:
                await ctx.send(part)
        else:
            await ctx.send(response)
            
    except Exception as e:
        logging.error(f"Ошибка в команде последние: {e}")
        await ctx.send("Произошла ошибка при получении последних сообщений")


# Пример использования в команде
@bot.command(name="проверить")
async def проверить(ctx):
    """Проверяет последнее сообщение в канале"""
    try:
        channel = bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        if not channel:
            await ctx.send("Канал не найден!")
            return
            
        result = await read_channel_message(channel)
        if result[0] is None:
            await ctx.send("Не удалось прочитать сообщение из канала.")
            return
            
        message, is_bot = result
            
        if is_bot:
            await ctx.send(f"✅ Последнее сообщение отправлено ботом: {message.content}")
        else:
            await ctx.send(f"👤 Последнее сообщение отправлено пользователем {message.author}: {message.content}")
            
    except Exception as e:
        logging.error(f"Ошибка в команде проверить: {e}")
        await ctx.send("Произошла ошибка при проверке сообщения")

@bot.command(name="график")
async def get_plot_avg_chats(ctx):
    try:
        await ctx.send("📊 Создаю график среднего количества чатов за час...")
        
        # Получаем данные из базы данных
        results = db_manager.get_avg_chats_for_hour()
        
        if not results:
            await ctx.send("❌ Нет данных для построения графика")
            return
        
        # Разделяем часы и средние значения
        hours = [row[0] for row in results]
        avg_chats = [row[1] for row in results]
        
        # Создаем график
        plt.figure(figsize=(12, 6))
        bars = plt.bar(hours, avg_chats, width=0.8, color='skyblue', edgecolor='navy', alpha=0.7)
        
        # Добавляем значения на столбцы
        for bar, value in zip(bars, avg_chats):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                    f'{value:.1f}', ha='center', va='bottom', fontweight='bold')
        
        plt.xlabel('Час дня', fontsize=12, fontweight='bold')
        plt.ylabel('Среднее количество чатов', fontsize=12, fontweight='bold')
        plt.title('📈 Среднее количество чатов по часам', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3, axis='y')
        plt.xticks(hours)
        
        # Улучшаем внешний вид
        plt.tight_layout()
        
        # Сохраняем график в файл
        plt.savefig('chart.png', dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()  # Закрываем фигуру для освобождения памяти

        # Отправляем файл
        with open('chart.png', 'rb') as f:
            picture = discord.File(f, filename='chat_statistics.png')
            await ctx.send("✅ График готов!", file=picture)
        
        # Удаляем временный файл
        import os
        if os.path.exists('chart.png'):
            os.remove('chart.png')
        
    except Exception as e:
        logging.error(f"Ошибка в команде график: {e}")
        await ctx.send(f"❌ Произошла ошибка при создании графика: {str(e)}")

@bot.event
async def on_command_error(ctx, error):
    # Если ошибка связана с отсутствием роли
    if isinstance(error, commands.MissingRole):
        await ctx.send(f"⛔ {ctx.author.mention}, у вас нет прав для этой команды. Нужна роль **старший куратор**.")
    
    # Если ошибка связана с отсутствием любой из ролей (если используете has_any_role)
    elif isinstance(error, commands.MissingAnyRole):
        await ctx.send(f"⛔ {ctx.author.mention}, у вас нет прав. Нужна роль **старший куратор**.")
        
    # Если команда не найдена (опционально, можно убрать)
    elif isinstance(error, commands.CommandNotFound):
        pass # Игнорируем, если пишут бред
        
    else:
        # Остальные ошибки логируем
        logging.error(f"Ошибка команды: {error}")
        # Можно раскомментировать для отладки:
        # await ctx.send(f"Произошла ошибка: {error}")

@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")
    logging.info(f"Бот {bot.user} запущен!")
    logging.info("База данных подключена и готова к работе")

    # --- УМНАЯ ПРОВЕРКА ЗАПУСКА ---
    # Получаем сохраненную задачу (если есть)
    existing_task = getattr(bot, 'periodic_task_object', None)

    # Проверяем:
    # 1. Задача вообще существует?
    # 2. Если существует, она всё ещё выполняется? (not .done())
    if existing_task and not existing_task.done():
        logging.info("Цикл уже активно работает, повторный запуск не требуется.")
        return
    
    # Если мы здесь — значит, задачи нет или она умерла. Запускаем новую.
    logging.info("Запускаем (или перезапускаем) фоновую задачу...")

    # !!! ВНИМАНИЕ: Здесь исправлен отступ (ровно 4 пробела) !!!
    async def periodic_task():
        """
        Основной цикл задач бота:
        1. В XX:00 — Собирает статистику и обновляет таблицы.
        2. В XX:05 — Проверяет, совпадает ли расписание с реальностью.
        """
        await bot.wait_until_ready()
        
        # Инициализация хранилища данных последнего часа (если его нет)
        if not hasattr(bot, 'last_collected_data'):
            bot.last_collected_data = {}

        while not bot.is_closed():
            try:
                now = datetime.now()
                # Если у вас сервер в UTC, а нужна Москва, раскомментируйте:
                # now = datetime.now(timezone.utc) + timedelta(hours=3)

                # ==========================================
                # ЛОГИКА 1: ЗАПИСЬ ДАННЫХ (XX:00)
                # ==========================================
                if now.minute == 0:
                    logging.info(f"Запуск ежечасного сбора данных ({now.strftime('%H:%M')})...")
                    
                    # 1. Собираем данные через ваш коллектор
                    # Предполагаем, что collector инициализирован в main или глобально
                    # Если collector внутри main, лучше прицепить его к боту: bot.collector = collector
                    curator_data = await bot.loop.run_in_executor(None, collector.collect_data)
                    
                    # Сохраняем в память бота для проверки через 5 минут
                    bot.last_collected_data = curator_data
                    
                    # 2. Обновляем таблицы
                    # update_schedule=True -> пытаемся записать имена в расписание
                    conflicts = await bot.loop.run_in_executor(None, lambda: update_both_tables(
                        SPREADSHEET_ID_STATS, 
                        SPREADSHEET_ID_SCHEDULE, 
                        curator_data, 
                        now.hour, 
                        now.strftime("%d"), 
                        MONTHS_GENITIVE[now.month], 
                        now, 
                        update_schedule=True
                    ))

                    # 3. Если при записи возникли конфликты (кто-то был записан, но не работал)
                    if conflicts and LOG_CHANNEL_ID:
                        try:
                            # Авторизация для получения имени старшего
                            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
                            client = gspread.authorize(creds)
                            
                            # Узнаем, кто старший на текущий час
                            senior_name = get_senior_for_hour(client, SPREADSHEET_ID_SCHEDULE, now, now.hour)
                            senior_tag = get_tag_by_name(senior_name) if senior_name else "Старший куратор"
                            
                            channel = bot.get_channel(LOG_CHANNEL_ID)
                            if channel:
                                conflicts_str = ", ".join(conflicts)
                                await channel.send(
                                    f"✏️ **Конфликт записи ({now.hour}:00)**\n"
                                    f"{senior_tag}, внимание!\n"
                                    f"В слотах уже были записаны люди, не сдавшие отчет: `{conflicts_str}`\n"
                                    f"*(Я их не удалял, а работающих дописал в пустые места)*."
                                )
                        except Exception as e:
                            logging.error(f"Ошибка при отправке алерта о конфликте записи: {e}")

                # ==========================================
                # ЛОГИКА 2: ПРОВЕРКА ПРОГУЛЬЩИКОВ (XX:05)
                # ==========================================
                elif now.minute == CHECK_MINUTES:
                    # Проверяем прошлый час. Если сейчас 15:05, проверяем смену 14:00-15:00
                    check_hour = now.hour - 1
                    check_dt = now
                    
                    # Обработка перехода через полночь (00:05 проверяет 23:00 вчера)
                    if check_hour < 0:
                        check_hour = 23
                        check_dt = now - timedelta(days=1)

                    # Проверяем только если у нас ЕСТЬ данные за прошлый час
                    if bot.last_collected_data:
                        logging.info(f"Проверка расписания за {check_hour}:00...")
                        try:
                            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
                            client = gspread.authorize(creds)

                            # 1. Кто должен был работать (из таблицы)
                            scheduled_names = get_scheduled_workers(client, SPREADSHEET_ID_SCHEDULE, check_dt, check_hour)
                            
                            # 2. Кто реально работал (из памяти бота)
                            # keys() возвращает имена кураторов, которые сдали отчет
                            worked_names = list(bot.last_collected_data.keys())

                            # 3. Старший на смене
                            senior_name = get_senior_for_hour(client, SPREADSHEET_ID_SCHEDULE, check_dt, check_hour)
                            senior_tag = get_tag_by_name(senior_name) if senior_name else "Неизвестный старший"

                            # 4. Поиск прогульщиков
                            absent_curators = []
                            for name in scheduled_names:
                                if name not in worked_names:
                                    absent_curators.append(name)
                            
                            # 5. Отправка отчета
                            if absent_curators and LOG_CHANNEL_ID:
                                channel = bot.get_channel(LOG_CHANNEL_ID)
                                if channel:
                                    # Превращаем имена прогульщиков в теги
                                    absent_tags = [get_tag_by_name(name) for name in absent_curators]
                                    absent_str = ", ".join(absent_tags)
                                    
                                    await channel.send(
                                        f"⚠️ **Несовпадение расписания ({check_hour}:00 - {check_hour+1}:00)**\n"
                                        f"Старший на смене: {senior_tag}\n\n"
                                        f"Стояли в графике, но не сдали отчет:\n{absent_str}"
                                    )
                        except Exception as e:
                            logging.error(f"Ошибка в блоке проверки расписания: {e}", exc_info=True)
                    else:
                        logging.warning("Пропуск проверки расписания: нет данных last_collected_data.")

                # ==========================================
                # 3. УМНЫЙ СОН (Выравнивание по минутам)
                # ==========================================
                # Гарантирует, что бот проснется ровно в :00 секунд следующей минуты
                now_after_work = datetime.now()
                seconds_to_sleep = 60 - now_after_work.second
                
                if seconds_to_sleep < 0: 
                    seconds_to_sleep = 1
                
                # Логируем долгий сон только если не выполняли работу (чтобы не спамить)
                if now.minute != 0 and now.minute != CHECK_MINUTES:
                # Можно уменьшить частоту логов, если мешает
                pass
                
                await asyncio.sleep(seconds_to_sleep + 0.5) # +0.5 для гарантии перехода на новую минуту

            except Exception as e:
                logging.error(f"Критическая ошибка в periodic_task: {e}", exc_info=True)
                await asyncio.sleep(60) # Спим минуту при ошибке, чтобы не дудосить сервер

    # СОХРАНЯЕМ ОБЪЕКТ ЗАДАЧИ В БОТА
    # Теперь мы не просто True ставим, а сохраняем ссылку на живой процесс
    bot.periodic_task_object = bot.loop.create_task(periodic_task())


if __name__ == "__main__":
    logging.info("Запуск Discord бота...")
    logging.info(f"Токен: {TOKEN[:10]}...")
    logging.info(f"Guild ID: {GUILD_ID}")
    logging.info(f"Channel ID: {CHANNEL_ID}")
    db_manager = DatabaseManager("bot_database.db")
    collector = DataCollector(db_manager)
    
    bot.collector = collector
    bot.run(TOKEN)