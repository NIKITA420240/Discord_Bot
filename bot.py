import os
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Импортируем классы логики
from ai_service import GeometryRAG 
from collect import DataCollector
from database import DatabaseManager

# --- Логирование ---
class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc) + timedelta(hours=3)
        if datefmt: return dt.strftime(datefmt)
        else: return dt.strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(MoscowFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)
# -------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN") # Читаем токен для AI
GUILD_ID = int(os.getenv("GUILD_ID"))

class MyBot(commands.Bot):
    def __init__(self):
        # Настраиваем интенты
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # Переменные для хранения сервисов
        self.collector = None
        self.rag_service = None # Здесь будет жить наш AI
        
        # Глобальные переменные состояния
        self.last_collection_hour = None
        self.last_reminder_hour = None
        self.last_collected_data = {}

    async def setup_hook(self):
        """
        Метод запускается ДО того, как бот подключится к Discord.
        Идеальное место для загрузки БД, AI моделей и Когов.
        """
        logging.info("🚀 Запуск setup_hook...")

        # 1. Инициализация БД и Коллектора
        db_manager = DatabaseManager("bot_database.db")
        self.collector = DataCollector(db_manager)
        logging.info("✅ Database & Collector инициализированы")

        # 2. Инициализация AI (RAG Service)
        if HF_TOKEN:
            logging.info("🧠 Инициализация AI RAG сервиса... (Загрузка модели в память)")
            try:
                # Создаем экземпляр класса. Это может занять 5-10 секунд.
                self.rag_service = GeometryRAG(HF_TOKEN)
                logging.info("✅ RAG сервис успешно загружен и готов к работе")
            except Exception as e:
                logging.error(f"❌ Ошибка загрузки AI сервиса: {e}")
                self.rag_service = None
        else:
            logging.warning("⚠️ HF_TOKEN не найден в .env! Команды AI поиска работать не будут.")

        # 3. Загрузка когов
        cogs_list = [
            'cogs.admin', 
            'cogs.stats', 
            'cogs.tasks', 
            'cogs.fun', 
            'cogs.backups', 
            'cogs.report', 
            # 'cogs.slash', 
            'cogs.library' 
        ]
        
        for cog in cogs_list:
            try:
                await self.load_extension(cog)
                logging.info(f"🧩 Модуль загружен: {cog}")
            except Exception as e:
                logging.error(f"❌ Ошибка загрузки модуля {cog}: {e}")

    async def on_ready(self):
        logging.info(f"🤖 Бот {self.user} подключился к Discord!")
        logging.info(f"🌍 Guild ID: {GUILD_ID}")
        
        # Синхронизация слэш-команд
        try:
            synced = await self.tree.sync()
            logging.info(f"🔄 Синхронизировано {len(synced)} слэш-команд(ы)")
        except Exception as e:
            logging.error(f"❌ Ошибка синхронизации команд: {e}")

if __name__ == "__main__":
    if not TOKEN:
        logging.critical("❌ DISCORD_TOKEN не найден! Проверь .env файл.")
    else:
        bot = MyBot()
        bot.run(TOKEN)