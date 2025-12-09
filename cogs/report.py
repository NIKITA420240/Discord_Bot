import discord
from discord.ext import commands, tasks
import os
import logging
import sqlite3
import requests
from datetime import datetime, timedelta, time, timezone

# Библиотеки для PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class WeeklyReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        self.db_path = "bot_database.db"
        self.font_path = "Arial.ttf"
        
        # Скачиваем шрифт, если его нет (для поддержки кириллицы)
        self.download_font_if_needed()
        
        # Запускаем задачу
        self.report_task.start()

    def download_font_if_needed(self):
        if not os.path.exists(self.font_path):
            logging.info("📥 Скачиваю шрифт Arial для PDF...")
            try:
                # Ссылка на свободный шрифт (LiberationSans похож на Arial)
                url = "https://github.com/liberationfonts/liberation-fonts/raw/main/liberation-fonts-ttf/LiberationSans-Regular.ttf"
                response = requests.get(url)
                with open(self.font_path, 'wb') as f:
                    f.write(response.content)
                logging.info("✅ Шрифт скачан.")
            except Exception as e:
                logging.error(f"❌ Не удалось скачать шрифт: {e}")

    def cog_unload(self):
        self.report_task.cancel()

    # Запуск каждое воскресенье в 23:00 МСК
    @tasks.loop(time=time(hour=20, minute=0)) # 20:00 UTC = 23:00 МСК
    async def report_task(self):
        # Проверка на воскресенье (0=Пн, 6=Вс)
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        if now.weekday() == 6:
            await self.generate_and_send_pdf()

    async def generate_and_send_pdf(self):
        if not self.log_channel_id:
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            return

        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"Otchet_{date_str}.pdf"

        try:
            data = self.get_weekly_stats()
            # Генерируем PDF (в отдельном потоке, чтобы не блочить бота)
            await self.bot.loop.run_in_executor(None, self.create_pdf, filename, data)
            
            file = discord.File(filename)
            await channel.send(
                f"📊 **Еженедельный отчет ({date_str})**\nСтатистика работы кураторов.", 
                file=file
            )
            logging.info(f"PDF отчет отправлен: {filename}")
        except Exception as e:
            logging.error(f"Ошибка генерации PDF: {e}")
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def get_weekly_stats(self):
        """Данные за последние 7 дней"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
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
        # Регистрация шрифта
        if os.path.exists(self.font_path):
            pdfmetrics.registerFont(TTFont('Arial', self.font_path))
            font_name = 'Arial'
        else:
            font_name = 'Helvetica' # Кириллица не будет работать

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        
        # Стили
        styles = getSampleStyleSheet()
        style_title = ParagraphStyle('MyTitle', parent=styles['Heading1'], fontName=font_name, alignment=1)
        style_body = ParagraphStyle('MyBody', parent=styles['Normal'], fontName=font_name)

        # Заголовок
        elements.append(Paragraph(f"Отчет за неделю", style_title))
        elements.append(Paragraph(f"Сформирован: {datetime.now().strftime('%d.%m.%Y')}", style_body))
        elements.append(Spacer(1, 20))

        # Таблица
        headers = ['Имя куратора', 'Всего чатов', 'Часов']
        table_data = [headers]
        
        total_chats = 0
        total_hours = 0

        for row in data:
            name, chats, hours = row
            total_chats += chats
            total_hours += hours
            table_data.append([str(name), str(chats), str(hours)])

        # Итого
        table_data.append(['ИТОГО:', str(total_chats), str(total_hours)])

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), font_name),
        ]))
        
        elements.append(t)
        doc.build(elements)

    @commands.command(name="отчет")
    @commands.has_any_role("Старший куратор", "Admin", "Administrator")
    async def manual_report(self, ctx):
        """Ручная генерация отчета"""
        await ctx.send("⏳ Генерирую PDF...")
        await self.generate_and_send_pdf()
        await ctx.send("✅ Готово.")

async def setup(bot):
    await bot.add_cog(WeeklyReport(bot))