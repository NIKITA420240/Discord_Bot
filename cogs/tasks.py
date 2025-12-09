import discord
from discord.ext import commands, tasks
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sheets import update_both_tables
from utils import Time_to_send, CHECK_MINUTES

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
        self.LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0))
        self.SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
        self.SPREADSHEET_ID_WORK_HOURS = os.getenv("SPREADSHEET_ID_WORK_HOURS")
        self.SPREADSHEET_ID_SCHEDULE = os.getenv("SPREADSHEET_ID_SCHEDULE")
        
        # Запуск цикла
        self.bg_task = self.bot.loop.create_task(self.periodic_task())

    def cog_unload(self):
        self.bg_task.cancel()

    async def update_sheet(self, force_schedule_update=False):
        """Логика обновления: Скрапинг -> БД -> Async Google Sheets"""
        guild = self.bot.get_guild(self.GUILD_ID)
        if not guild: return {}, 0, 0, "", False, []
        channel = guild.get_channel(self.CHANNEL_ID)
        if not channel: return {}, 0, 0, "", False, []

        # 1. Скрапинг чата
        scrape_result = await self.bot.collector.collect_discord_data(channel)
        _, hour, day, month_name, dt_obj = scrape_result
        
        message_date_str = dt_obj.strftime('%Y-%m-%d')

        # 2. Полные данные из БД
        curator_data = self.bot.collector.db_manager.get_curator_stats_for_hour(message_date_str, hour)
        
        logging.info(f"📤 Отправка в Google Sheets: {len(curator_data)} записей (Async)")

        if curator_data:
            # Вызываем асинхронную функцию напрямую
            is_success, conflicts = await update_both_tables(
                self.SPREADSHEET_ID, 
                self.SPREADSHEET_ID_WORK_HOURS, 
                curator_data, hour, day, month_name, dt_obj,
                force_schedule_update
            )
            return curator_data, hour, day, month_name, is_success, conflicts
        else:
            return {}, hour, day, month_name, True, []

    async def periodic_task(self):
        await self.bot.wait_until_ready()
        logging.info("⏳ Фоновая задача (Tasks Cog) запущена.")
        
        while not self.bot.is_closed():
            try:
                now = datetime.now(timezone.utc) + timedelta(hours=3)
                channel = self.bot.get_channel(self.CHANNEL_ID)

                # 1. Напоминание
                if now.minute == Time_to_send:
                    if self.bot.last_reminder_hour != now.hour:
                        if channel:
                            await channel.send(f"Пишите количество чатов за {now.hour} час. НЕ ПИШИТЕ в {Time_to_send} МИНУТ!!!")
                            logging.info(f"🔔 Напоминание отправлено: {now.hour}:00")
                        self.bot.last_reminder_hour = now.hour

                # 2. Сбор данных (xx:05)
                elif now.minute == 5:
                    if self.bot.last_collection_hour != now.hour:
                        logging.info(f"🚀 Авто-сбор данных за {now.hour}:00...")
                        data, c_hour, _, _, success, conflicts = await self.update_sheet(force_schedule_update=True)
                        
                        if success:
                            self.bot.last_collected_data = data
                            self.bot.last_collection_hour = c_hour
                        
                        if conflicts and self.LOG_CHANNEL_ID:
                            log_ch = self.bot.get_channel(self.LOG_CHANNEL_ID)
                            if log_ch:
                                await log_ch.send(f"✏️ **Конфликт записи:** {', '.join(conflicts)}")

                # Умный сон
                sleep_sec = 60 - datetime.now().second
                await asyncio.sleep(sleep_sec + 0.5)

            except Exception as e:
                logging.error(f"Ошибка в цикле задач: {e}")
                await asyncio.sleep(60)

async def setup(bot):
    await bot.add_cog(Tasks(bot))