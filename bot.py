import os
import asyncio
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from utils import Time_to_send
import sys

from collect import collect_discord_data
from sheets import update_google_sheets

# Логирование
class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc) + timedelta(hours=3)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime("%Y-%m-%d %H:%M:%S")

handler = logging.FileHandler("bot.log", encoding="utf-8")
formatter = MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[handler])


# Загрузка переменных
load_dotenv()
# Переменная для отправки сообщения только один раз в час
last_sent_hour = None

def get_env_var(name, required=True) -> str:
    value = os.getenv(name)
    if required and value is None:
        logging.error(f"Не найдена переменная окружения: {name}. Завершаем работу.")
        remove_lock()
        sys.exit(1)
    return str(value)

TOKEN = get_env_var("DISCORD_TOKEN")
SPREADSHEET_ID = get_env_var("SPREADSHEET_ID")
GUILD_ID = int(get_env_var("GUILD_ID"))
CHANNEL_ID = int(get_env_var("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

black_users = set()

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.lock')

def create_lock():
    abs_path = os.path.abspath(LOCK_FILE)
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, 'r') as f:
            pid = f.read().strip()
        logging.error(f'Бот уже запущен! Lock-файл: {abs_path}, PID: {pid}. Завершаем работу.')
        sys.exit(1)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    logging.info(f"Lock file создан: {abs_path}, PID: {os.getpid()}")

def remove_lock():
    abs_path = os.path.abspath(LOCK_FILE)
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        logging.info(f"Lock file удалён: {abs_path}")

async def update_sheet():
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(CHANNEL_ID)

    if not guild:
        logging.error("Сервер не найден!")
        return {}
    if not channel:
        logging.error("Канал не найден")
        return {}

    curator_data, hour, day, month_name = await collect_discord_data(channel, black_users)
    success = update_google_sheets(SPREADSHEET_ID, curator_data, hour, day, month_name)
    return curator_data, hour, day, month_name, success

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
        curator_data, hour, day, month_name = await collect_discord_data(
            bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID), black_users
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

@bot.event
async def on_ready():
    logging.info(f"Бот {bot.user} запущен!")

    # Периодическое обновление
    async def periodic_task():
        global last_sent_hour
        await bot.wait_until_ready()
        channel = bot.get_guild(GUILD_ID).get_channel(CHANNEL_ID)
        while not bot.is_closed():
            try:
                now = datetime.now() + timedelta(hours=3)
                if (now.minute == Time_to_send) and (8 <= now.hour < 23) and last_sent_hour != now.hour:
                    try:
                        await channel.send(f"Пишите количество чатов за {now.hour} час")
                        logging.info(f"Отправляем сообщение, о том что нужно написать количество чатов за час {now.hour}.")
                        last_sent_hour = now.hour
                        await asyncio.sleep(61)  # Спим 61 секунду, чтобы не отправить повторно
                    except Exception as e:
                        logging.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
                else:
                    await update_sheet()
                    logging.info("Периодическое обновление...")
                    await asyncio.sleep(20)
            except Exception as e:
                logging.error(f"Ошибка в периодическом обновлении: {e}", exc_info=True)     

    bot.loop.create_task(periodic_task())

def main():
    bot.run(TOKEN)

if __name__ == "__main__":
    try:
        create_lock()
        main()
    finally:
        remove_lock()
