import os
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import discord
from discord.ext import commands

from collect import DataCollector
from database import DatabaseManager

# --- Логирование (оставляем как было) ---
class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc) + timedelta(hours=3)
        if datefmt: return dt.strftime(datefmt)
        else: return dt.strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Очистка хендлеров для предотвращения дублей
if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)
# ----------------------------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.collector = None # Будет инициализирован при старте
        
        # Глобальные переменные состояния (перенесены из старого bot.py)
        self.last_collection_hour = None
        self.last_reminder_hour = None
        self.last_collected_data = {}

    async def setup_hook(self):
        # Инициализация БД и Коллектора
        db_manager = DatabaseManager("bot_database.db")
        self.collector = DataCollector(db_manager)
        
        # Загрузка когов (модулей)
        cogs_list = ['cogs.admin', 'cogs.stats', 'cogs.tasks', 'cogs.fun', 'cogs.backups', 'cogs.report']
        for cog in cogs_list:
            try:
                await self.load_extension(cog)
                logging.info(f"🧩 Модуль загружен: {cog}")
            except Exception as e:
                logging.error(f"Ошибка загрузки модуля {cog}: {e}")

    async def on_ready(self):
        logging.info(f"Бот {self.user} запущен! (Режим Cogs)")
        logging.info(f"Guild ID: {GUILD_ID}")
        
        # --- ДОБАВЛЕНО: Синхронизация слэш-команд ---
        try:
            synced = await self.tree.sync()
            logging.info(f"🔄 Синхронизировано {len(synced)} слэш-команд(ы)")
        except Exception as e:
            logging.error(f"❌ Ошибка синхронизации команд: {e}")

if __name__ == "__main__":
    bot = MyBot()
    bot.run(TOKEN)