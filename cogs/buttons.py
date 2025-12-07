import discord
from discord.ext import commands
from discord import ui
import logging
from datetime import datetime, timezone, timedelta

# Импортируем нашу БД (чтобы сохранять отчеты сразу)
from database import DatabaseManager

class ReportModal(ui.Modal, title="Отчет за час"):
    # Поле ввода
    chats_count = ui.TextInput(
        label="Количество чатов",
        placeholder="Например: 15",
        min_length=1,
        max_length=3,
        required=True
    )

    def __init__(self, db_manager, bot_user):
        super().__init__()
        self.db_manager = db_manager
        self.bot = bot_user # Ссылка на бота, чтобы обновить кэш

    async def on_submit(self, interaction: discord.Interaction):
        # Получаем данные
        value = self.chats_count.value
        
        # Проверка, что это число
        if not value.isdigit():
            await interaction.response.send_message("❌ Ошибка: Введите только число!", ephemeral=True)
            return
            
        count = int(value)
        
        # Данные пользователя
        user_id = interaction.user.id
        username = interaction.user.display_name # Или name, зависит от того, как у вас в users.py
        
        # Время (МСК)
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        
        try:
            # 1. Сохраняем в БД напрямую
            self.db_manager.save_message(
                user_id=user_id,
                username=username,
                message_text=str(count), # Сохраняем как будто он написал сообщение
                message_date=now
            )
            
            # 2. Обновляем локальный кэш бота (чтобы !покажи видело изменения сразу)
            # Формируем имя для ключа (как в users.py нормализация)
            # Лучше использовать display_name, бот сам разберется в маппинге
            if self.bot.last_collected_data is None:
                self.bot.last_collected_data = {}
            self.bot.last_collected_data[username] = count

            await interaction.response.send_message(f"✅ Принято: **{count}** чатов за {now.hour}:00.", ephemeral=True)
            logging.info(f"[BUTTON] {username} сдал отчет: {count}")
            
        except Exception as e:
            logging.error(f"Ошибка сохранения через кнопку: {e}")
            await interaction.response.send_message("❌ Ошибка базы данных.", ephemeral=True)

class ReportView(ui.View):
    def __init__(self, db_manager, bot):
        super().__init__(timeout=None) # Кнопка вечная (пока бот работает)
        self.db_manager = db_manager
        self.bot = bot

    @ui.button(label="📝 Сдать отчет", style=discord.ButtonStyle.success, custom_id="report_button")
    async def report_button(self, interaction: discord.Interaction, button: ui.Button):
        # Открываем модальное окно
        await interaction.response.send_modal(ReportModal(self.db_manager, self.bot))

class Buttons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Слушатель, который запускается при старте бота, чтобы кнопки работали после перезагрузки
    # (Если вы будете использовать Persistent Views, но пока сделаем просто отправку новой кнопки каждый час)
    
async def setup(bot):
    await bot.add_cog(Buttons(bot))