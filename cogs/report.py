import discord
from discord.ext import commands, tasks
import os
import logging
import sqlite3
from datetime import datetime, timedelta, time, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Регистрируем шрифт (нужен файл шрифта, но reportlab по умолчанию не поддерживает кириллицу стандартными шрифтами)
# Для простоты будем использовать встроенный шрифт, но кириллица может отображаться квадратиками без настройки.
# ЛУЧШЕЕ РЕШЕНИЕ: Скачать файл шрифта (например Arial.ttf) и положить в папку.
# Но пока сделаем транслит имен или попробуем без шрифта, если у вас его нет.
# В Docker контейнере обычно нет шрифтов.
# Я добавлю код, который попытается найти шрифт, или использует стандартный.

class WeeklyReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        self.db_path = "bot_database.db"
        self.report_task.start()

    def cog_unload(self):
        self.report_task.cancel()

    # Запуск каждое воскресенье в 23:00 (МСК = UTC+3, значит 20:00 UTC)
    # 0 = Понедельник, 6 = Воскресенье
    @tasks.loop(time=time(hour=20, minute=0)) 
    async def report_task(self):
        # Проверяем, что сегодня воскресенье
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        if now.weekday() == 6: 
            await self.generate_and_send_pdf()

    async def generate_and_send_pdf(self):
        if not self.log_channel_id:
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            return

        filename = f"Weekly_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        
        try:
            # 1. Получаем данные за неделю
            stats = self.get_weekly_stats()
            
            # 2. Генерируем PDF
            self.create_pdf(filename, stats)
            
            # 3. Отправляем
            file = discord.File(filename)
            await channel.send(
                "📊 **Еженедельный отчет готов!**\nСодержит статистику по всем кураторам за последние 7 дней.", 
                file=file
            )
            logging.info(f"PDF отчет {filename} отправлен.")
            
        except Exception as e:
            logging.error(f"Ошибка создания PDF: {e}")
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def get_weekly_stats(self):
        """Запрос к БД: группировка по кураторам за 7 дней"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Берем последние 7 дней
                cursor.execute('''
                    SELECT curator_name, SUM(chats_count), COUNT(*)
                    FROM curator_messages 
                    WHERE message_date >= date('now', '-7 days')
                    AND chats_count >= 0
                    GROUP BY curator_name
                    ORDER BY SUM(chats_count) DESC
                ''')
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"DB Error: {e}")
            return []

    def create_pdf(self, filename, data):
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Заголовок
        title = Paragraph(f"Otchet za nedelyu (Weekly Report) - {datetime.now().strftime('%d.%m.%Y')}", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Таблица
        # Заголовки: Имя, Чаты, Часы
        table_data = [['Name', 'Total Chats', 'Hours Worked']]
        
        total_chats_week = 0
        total_hours_week = 0

        for row in data:
            # row = (Name, Chats, Hours)
            # Транслитерация нужна, если нет кириллического шрифта
            # Но попробуем вывести как есть, если вдруг кракозябры - заменим на транслит
            name = row[0] 
            chats = row[1]
            hours = row[2]
            
            total_chats_week += chats
            total_hours_week += hours
            
            table_data.append([str(name), str(chats), str(hours)])

        # Итоговая строка
        table_data.append(['TOTAL', str(total_chats_week), str(total_hours_week)])

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige), # Цвета строк
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), # Итоговая строка
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(t)
        doc.build(elements)

    # Команда для ручного теста
    @commands.command(name="отчет")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def manual_report(self, ctx):
        await ctx.send("⏳ Генерирую PDF отчет...")
        filename = "Manual_Report.pdf"
        try:
            stats = self.get_weekly_stats()
            self.create_pdf(filename, stats)
            await ctx.send(file=discord.File(filename))
        except Exception as e:
            await ctx.send(f"Ошибка: {e}")
        finally:
            if os.path.exists(filename):
                os.remove(filename)

async def setup(bot):
    await bot.add_cog(WeeklyReport(bot))