import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta, timezone
import os

from sheets import get_scheduled_workers, get_senior_for_hour

def normalize_name(name):
    if not name: return ""
    return name.lower().replace('ё', 'е').strip()

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.SPREADSHEET_ID_SCHEDULE = os.getenv("SPREADSHEET_ID_SCHEDULE")

    def get_mention(self, ru_name):
        if not ru_name: return "Неизвестный"
        login = self.bot.collector.db_manager.get_discord_id_by_name(ru_name)
        if login:
            guild = self.bot.get_guild(self.GUILD_ID)
            if guild:
                member = discord.utils.get(guild.members, name=login)
                if member: return member.mention
        return ru_name

    # --- КОМАНДЫ УПРАВЛЕНИЯ КУРАТОРАМИ ---
    @commands.command(name="добавить")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def add_curator(self, ctx, member: discord.Member, *, full_name: str):
        discord_id = str(member.name)
        if self.bot.collector.db_manager.add_user(discord_id, full_name):
            await ctx.send(f"✅ Куратор добавлен: {member.mention} -> {full_name}")
            logging.info(f"Admin added user: {discord_id} -> {full_name}")
        else:
            await ctx.send("❌ Ошибка при добавлении в базу данных.")

    @commands.command(name="удалить")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def remove_curator(self, ctx, member: discord.Member):
        discord_id = str(member.name)
        if self.bot.collector.db_manager.remove_user(discord_id):
            await ctx.send(f"🗑️ Куратор удален: {member.mention}")
            logging.info(f"Admin removed user: {discord_id}")
        else:
            await ctx.send("❌ Куратор не найден или ошибка БД.")

    @commands.command(name="список")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def list_curators(self, ctx):
        users = self.bot.collector.db_manager.get_all_users()
        if not users:
            await ctx.send("База кураторов пуста.")
            return
            
        msg = "**Список кураторов:**\n"
        buffer = ""
        for login, name in users:
            line = f"`{login}`: {name}\n"
            if len(buffer) + len(line) > 1900:
                await ctx.send(buffer)
                buffer = line
            else:
                buffer += line
        if buffer:
            await ctx.send(buffer)

    # --- ОСНОВНЫЕ КОМАНДЫ ---
    @commands.command(name="обнови")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def обнови(self, ctx):
        await ctx.send("🔄 Собираю данные и принудительно обновляю таблицы (Async)...")
        tasks_cog = self.bot.get_cog('Tasks')
        if not tasks_cog:
            await ctx.send("❌ Ошибка: Модуль задач не загружен.")
            return

        data, hour, day, month_name, success, conflicts = await tasks_cog.update_sheet(force_schedule_update=True)
        
        if success:
            self.bot.last_collected_data = data
            self.bot.last_collection_hour = hour

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

        if self.bot.last_collection_hour is not None and self.bot.last_collection_hour != check_hour:
             await ctx.send(f"⚠️ **Внимание:** Вы проверяете прогульщиков на {check_hour}:00, но данные собраны за {self.bot.last_collection_hour}:00 (выполните `!обнови`, если нужно актуализировать).")

        await ctx.send(f"⚖️ **Сравниваю:** График на {check_hour}:00")

        try:
            # Вызываем асинхронную функцию (клиент создается внутри нее)
            scheduled = await get_scheduled_workers(self.SPREADSHEET_ID_SCHEDULE, now, check_hour)
            
            worked = list(self.bot.last_collected_data.keys())
            worked_norm = [normalize_name(n) for n in worked]
            absent = [name for name in scheduled if normalize_name(name) not in worked_norm]

            msg = f"📋 **По расписанию ({len(scheduled)}):** {', '.join(scheduled)}\n"
            msg += f"✅ **Сдали отчет ({len(worked)}):** {', '.join(worked)}\n"
            msg += "---------------------------------\n"
            
            if absent:
                mentions = [self.get_mention(name) for name in absent]
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
            workers = await get_scheduled_workers(self.SPREADSHEET_ID_SCHEDULE, now, now.hour)
            if workers:
                lines = [f"👤 {w} -> {self.get_mention(w)}" for w in workers]
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
            senior = await get_senior_for_hour(self.SPREADSHEET_ID_SCHEDULE, now, now.hour)
            if senior:
                await ctx.send(f"👑 **Старший:** {senior} ({self.get_mention(senior)})")
            else:
                await ctx.send("🤷‍♂️ Старший не найден.")
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}")

    @commands.command(name="очистить")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def очистить(self, ctx, days: int = 90):
        try:
            deleted = self.bot.collector.db_manager.delete_old_records(days)
            await ctx.send(f"🗑️ Удалено {deleted} записей старше {days} дней.")
        except Exception as e:
            await ctx.send(f"Ошибка: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))