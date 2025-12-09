import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime, timedelta, timezone
from utils import months_name, Time_to_send

class ReportModal(discord.ui.Modal, title="Отчет по чатам"):
    # Поле ввода
    chats_input = discord.ui.TextInput(
        label="Количество чатов",
        placeholder="Например: 42",
        min_length=1,
        max_length=4,
        required=True
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Проверяем, число ли это
        try:
            count = int(self.chats_input.value)
        except ValueError:
            await interaction.response.send_message("❌ Ошибка: Введите целое число!", ephemeral=True)
            return

        # 2. Определяем пользователя через БД
        user_id = str(interaction.user.name) # Используем username как ID
        real_name = self.bot.collector.db_manager.get_user_name(user_id)
        
        if not real_name:
            await interaction.response.send_message(
                f"❌ Вас нет в базе кураторов! Обратитесь к админу.\nВаш ID: `{user_id}`", 
                ephemeral=True
            )
            return

        # 3. Определяем время (логика как в collect.py)
        now = datetime.now(timezone.utc)
        # Если отчет отправлен до 55 минут, считаем, что это за текущий час по МСК? 
        # Используем ту же логику смещения, что и в collect.py для совместимости
        if now.minute < Time_to_send:
            msg_time = now + timedelta(hours=2) # Коррекция под логику бота
        else:
            msg_time = now + timedelta(hours=3)

        hour = msg_time.hour
        message_date = msg_time.strftime('%Y-%m-%d')
        day = msg_time.day
        month = months_name[msg_time.month - 1]

        # 4. Сохраняем в БД
        try:
            self.bot.collector.db_manager.add_curator_message(
                real_name,
                user_id,
                message_date,
                hour,
                count
            )
            
            # Ответ пользователю (виден только ему -> ephemeral=True)
            await interaction.response.send_message(
                f"✅ Принято: **{count}** чатов за **{hour}:00** ({day} {month}).", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка записи: {e}", ephemeral=True)

class Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))

    # Регистрируем команду /отчет
    @app_commands.command(name="отчет", description="Сдать отчет по количеству чатов")
    async def report_command(self, interaction: discord.Interaction):
        # Открываем модальное окно
        await interaction.response.send_modal(ReportModal(self.bot))

async def setup(bot):
    await bot.add_cog(Slash(bot))