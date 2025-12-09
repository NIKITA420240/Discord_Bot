import discord
from discord.ext import commands, tasks
import os
import logging
import zipfile
from datetime import time, datetime, timezone, timedelta

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Берем ID канала логов из .env
        self.log_channel_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        
        # Запускаем таймер (если модуль был перезагружен, таймер перезапустится)
        self.backup_task.start()

    def cog_unload(self):
        self.backup_task.cancel()

    # Бекап каждый день в 03:00 UTC (06:00 МСК)
    @tasks.loop(time=time(hour=3, minute=0))
    async def backup_task(self):
        await self.send_backup_to_discord()

    async def send_backup_to_discord(self):
        if not self.log_channel_id:
            logging.warning("⚠️ LOG_CHANNEL_ID не задан в .env. Бекап отменен.")
            return

        db_filename = "bot_database.db"
        if not os.path.exists(db_filename):
            logging.error(f"Файл {db_filename} не найден!")
            return

        # Получаем канал
        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            logging.error(f"⚠️ Канал логов {self.log_channel_id} не найден. Проверьте ID и права бота.")
            return

        zip_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

        try:
            # 1. Сжимаем базу в ZIP (текстовые базы сжимаются очень хорошо, в 5-10 раз)
            # Это позволит отправлять даже большие базы, не упираясь в лимит 25МБ
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(db_filename)

            # 2. Отправляем файл в канал
            now_str = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M")
            file = discord.File(zip_filename)
            
            await channel.send(
                f"📦 **Ежедневный бекап базы данных**\n📅 Дата: `{now_str}`", 
                file=file
            )
            logging.info(f"✅ Бекап {zip_filename} отправлен в Discord.")

        except Exception as e:
            logging.error(f"❌ Ошибка бекапа в Discord: {e}")
        
        finally:
            # 3. Удаляем временный архив, чтобы не занимать место в контейнере
            if os.path.exists(zip_filename):
                os.remove(zip_filename)

    @commands.command(name="бекап")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def manual_backup(self, ctx):
        """Ручной запуск бекапа в текущий канал"""
        status_msg = await ctx.send("⏳ Архивирую базу данных...")
        
        # Для ручного запуска используем тот же метод, но можем переопределить канал отправки
        # Чтобы отправить именно сюда (в ctx.channel), напишем логику тут:
        
        db_filename = "bot_database.db"
        zip_filename = "backup_manual.zip"
        
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(db_filename)
                
            await ctx.send(file=discord.File(zip_filename))
            await status_msg.edit(content="✅ Бекап отправлен.")
            
        except Exception as e:
            await status_msg.edit(content=f"❌ Ошибка: {e}")
        
        finally:
            if os.path.exists(zip_filename):
                os.remove(zip_filename)

async def setup(bot):
    await bot.add_cog(Backup(bot))