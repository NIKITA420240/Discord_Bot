import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta, timezone
import gspread
from google.oauth2.service_account import Credentials
import os

# Импорт ваших утилит
from utils import SCOPES, CREDENTIALS_FILE
from sheets import get_scheduled_workers, get_senior_for_hour, update_both_tables
from users import get_login_by_name

# Вспомогательная функция для меншенов (копируем сюда или импортируем)
def get_mention(ru_name, guild):
    if not ru_name: return "Неизвестный"
    login = get_login_by_name(ru_name)
    if login and guild:
        member = discord.utils.get(guild.members, name=login)
        if member: return member.mention
    return ru_name

def normalize_name(name):
    if not name: return ""
    return name.lower().replace('ё', 'е').strip()

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.CREDENTIALS_FILE = CREDENTIALS_FILE
        self.SCOPES = SCOPES
        self.SPREADSHEET_ID_SCHEDULE = os.getenv("SPREADSHEET_ID_SCHEDULE")

    @commands.command(name="обнови")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def обнови(self, ctx):
        await ctx.send("🔄 Собираю данные и принудительно обновляю таблицы...")
        
        # Вызываем функцию update_sheet из модуля Tasks
        tasks_cog = self.bot.get_cog('Tasks')
        if not tasks_cog:
            await ctx.send("❌ Ошибка: Модуль задач не загружен.")
            return

        # force_schedule_update=True
        data, hour, day, month_name, success, conflicts = await tasks_cog.update_sheet(force_schedule_update=True)
        
        status = "успешно" if success else "с ошибками"
        msg = f"✅ Готово! Статус: {status}.\nОбработано: {len(data)} записей за {day} {month_name}, {hour}:00."
        if conflicts:
            msg += f"\n\n⚠️ **Найдены конфликты:**\n{', '.join(conflicts)}"
        await ctx.send(msg)

    @commands.command(name="тест_прогул")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def тест_прогул(self, ctx):
        if not self.bot.last_collected_data:
            await ctx.send("⚠️ Нет данных в памяти. Сначала выполните `!обнови`.")
            return

        now = datetime.now(timezone.utc) + timedelta(hours=3)
        check_hour = now.hour
        await ctx.send(f"⚖️ **Сравниваю:** График на {check_hour}:00")

        try:
            creds = Credentials.from_service_account_file(self.CREDENTIALS_FILE, scopes=self.SCOPES)
            client = gspread.authorize(creds)

            scheduled = await self.bot.loop.run_in_executor(
                None, get_scheduled_workers, client, self.SPREADSHEET_ID_SCHEDULE, now, check_hour
            )
            worked = list(self.bot.last_collected_data.keys())
            
            worked_norm = [normalize_name(n) for n in worked]
            absent = [name for name in scheduled if normalize_name(name) not in worked_norm]

            msg = f"📋 **По расписанию ({len(scheduled)}):** {', '.join(scheduled)}\n"
            msg += f"✅ **Сдали отчет ({len(worked)}):** {', '.join(worked)}\n"
            msg += "---------------------------------\n"
            
            if absent:
                guild = self.bot.get_guild(self.GUILD_ID)
                mentions = [get_mention(name, guild) for name in absent]
                msg += f"🚨 **ПРОГУЛЬЩИКИ:** {', '.join(mentions)}"
            else:
                msg += "✨ **Все на месте!**"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: ```{e}```")

    @commands.command(name="смена")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def смена(self, ctx):
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        await ctx.send(f"🔎 Читаю график на **{now.hour}:00**...")
        try:
            creds = Credentials.from_service_account_file(self.CREDENTIALS_FILE, scopes=self.SCOPES)
            client = gspread.authorize(creds)
            workers = await self.bot.loop.run_in_executor(
                None, get_scheduled_workers, client, self.SPREADSHEET_ID_SCHEDULE, now, now.hour
            )
            if workers:
                guild = self.bot.get_guild(self.GUILD_ID)
                lines = [f"👤 {w} -> {get_mention(w, guild)}" for w in workers]
                await ctx.send(f"✅ **В графике ({len(workers)}):**\n" + "\n".join(lines))
            else:
                await ctx.send("🕸️ В графике никого нет.")
        except Exception as e:
            await ctx.send(f"❌ Ошибка: ```{e}```")
            
    @commands.command(name="старший")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def старший(self, ctx):
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        try:
            creds = Credentials.from_service_account_file(self.CREDENTIALS_FILE, scopes=self.SCOPES)
            client = gspread.authorize(creds)
            senior = await self.bot.loop.run_in_executor(
                None, get_senior_for_hour, client, self.SPREADSHEET_ID_SCHEDULE, now, now.hour
            )
            if senior:
                guild = self.bot.get_guild(self.GUILD_ID)
                await ctx.send(f"👑 **Старший:** {senior} ({get_mention(senior, guild)})")
            else:
                await ctx.send("🤷‍♂️ Старший не найден.")
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}")

    @commands.command(name="очистить")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def очистить(self, ctx, days: int = 90):
        try:
            # Для доступа к db_manager нужен доступ к коллектору или напрямую
            # В bot.py мы привязали collector к боту
            deleted = self.bot.collector.db_manager.delete_old_records(days)
            await ctx.send(f"🗑️ Удалено {deleted} записей старше {days} дней.")
        except Exception as e:
            await ctx.send(f"Ошибка: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))