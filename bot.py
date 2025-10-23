from operator import truediv
import os
import asyncio
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from utils import Time_to_send
import sys
import matplotlib.pyplot as plt

from collect import DataCollector
from database import DatabaseManager
from sheets import update_google_sheets

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
GUILD_ID = int(get_env_var("GUILD_ID"))
CHANNEL_ID = int(get_env_var("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Инициализация базы данных
db_manager = DatabaseManager()
data_collector = DataCollector(db_manager)

# Переменная для хранения времени последнего отправления
last_sent = None

# Логируем после инициализации
logging.info("Discord бот инициализирован")
logging.info("База данных подключена")

async def update_sheet():
    """Обновляет Google Sheets и базу данных"""
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(CHANNEL_ID)

    if not guild:
        logging.error("Сервер не найден!")
        return {}
    if not channel:
        logging.error("Канал не найден")
        return {}

    curator_data, hour, day, month_name, _ = await data_collector.collect_discord_data(channel)
    
    # Обновляем Google Sheets (опционально)
    if curator_data:
        success = update_google_sheets(SPREADSHEET_ID, curator_data, hour, day, month_name)
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
async def обнови(ctx):
    await ctx.send("Собираю данные и обновляю таблицу...")
    curator_data, hour, day, month_name, success = await update_sheet()
    status = "успешно" if success else "с ошибками"
    await ctx.send(f"Готово! Статус: {status}. Обработано: {len(curator_data)} записей за {day} {month_name}, {hour}:00 часов.")

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
async def on_ready():
    print(f"Бот {bot.user} запущен!")
    logging.info(f"Бот {bot.user} запущен!")
    logging.info("База данных подключена и готова к работе")
    print("Бот готов к работе!")

    # Периодическое обновление
    async def periodic_task():
        await bot.wait_until_ready()
        channel = bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)

        # здесь будем хранить, за какой час уже отправили сообщение
        last_sent = None  

        while not bot.is_closed():
            try:
                now = datetime.now()

                # проверяем, что минута совпала и за этот час ещё не отправляли
                if (
                    now.minute == Time_to_send
                    and (await last_message_check_is_not_chats(channel))
                    and last_sent != (now.date(), now.hour)
                ):
                    await channel.send(f"Пишите количество чатов за {now.hour} час. НЕ ПИШИТЕ в {Time_to_send} МИНУТ!!! Дождитесь хотя-бы минуты.")
                    logging.info(f"Отправляем сообщение за {now.hour} час")

                    # запоминаем, что за этот час сообщение уже отправлено
                    last_sent = (now.date(), now.hour)

                    # спим до смены минуты, чтобы не сработать повторно
                    await asyncio.sleep(61)

                else:
                    # обычное обновление
                    await update_sheet()
                    logging.info("Периодическое обновление...")
                    await asyncio.sleep(20)

            except Exception as e:
                logging.error(f"Ошибка в periodic_task: {e}", exc_info=True)   

    bot.loop.create_task(periodic_task())


if __name__ == "__main__":
    logging.info("Запуск Discord бота...")
    logging.info(f"Токен: {TOKEN[:10]}...")
    logging.info(f"Guild ID: {GUILD_ID}")
    logging.info(f"Channel ID: {CHANNEL_ID}")
    bot.run(TOKEN)