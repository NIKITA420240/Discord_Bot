import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import os
import logging
from datetime import datetime

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

    @commands.command(name="покажи")
    async def покажи(self, ctx):
        try:
            guild = self.bot.get_guild(self.GUILD_ID)
            channel = guild.get_channel(self.CHANNEL_ID)
            
            # Используем коллектор бота
            result = await self.bot.collector.collect_discord_data(channel)
            curator_data, hour, day, month_name = result[0], result[1], result[2], result[3]
            
            if not curator_data:
                await ctx.send("Нет данных за последний час.")
                return
                
            msg = "**Последние данные:**\n"
            for name, count in curator_data.items():
                msg += f"- {name} [{day} {month_name}] [{hour}:00]: {count} чатов\n"
            await ctx.send(msg)
        except Exception as e:
            logging.error(f"Ошибка !покажи: {e}")
            await ctx.send("Ошибка при получении данных.")

    @commands.command(name="график")
    async def график(self, ctx):
        await ctx.send("📊 Рисую график...")
        try:
            # Обращаемся к БД через коллектор
            results = self.bot.collector.db_manager.get_avg_chats_for_hour()
            if not results:
                await ctx.send("❌ Нет данных.")
                return
            
            hours = [row[0] for row in results]
            avgs = [row[1] for row in results]
            
            plt.figure(figsize=(10, 5))
            bars = plt.bar(hours, avgs, color='skyblue', edgecolor='navy')
            plt.xlabel('Час')
            plt.ylabel('Среднее кол-во')
            plt.title('Активность по часам')
            plt.grid(axis='y', alpha=0.3)
            plt.xticks(hours)
            
            # Сохранение и отправка
            filename = 'chart_temp.png'
            plt.savefig(filename, bbox_inches='tight')
            plt.close()
            
            with open(filename, 'rb') as f:
                await ctx.send(file=discord.File(f, filename='stats.png'))
            os.remove(filename)
            
        except Exception as e:
            await ctx.send(f"Ошибка: {e}")

    @commands.command(name="топдетей")
    async def топдетей(self, ctx, days: int = 7):
        top = self.bot.collector.get_top_curators_count_sms(days, 10)
        if top:
            msg = f"**🏆 Топ по чатам ({days} дн.):**\n"
            for i, (name, count) in enumerate(top, 1):
                msg += f"{i}. {name}: {count}\n"
            await ctx.send(msg)
        else:
            await ctx.send("Нет данных.")

    @commands.command(name="топ")
    async def топ(self, ctx, days: int = 7):
        top = self.bot.collector.get_top_curators_count_hours(days, 10)
        if top:
            msg = f"**🏆 Топ по часам ({days} дн.):**\n"
            for i, (name, count) in enumerate(top, 1):
                msg += f"{i}. {name}: {count} ч.\n"
            await ctx.send(msg)
        else:
            await ctx.send("Нет данных.")

    @commands.command(name="история")
    async def история(self, ctx, *args):
        # Парсинг аргументов: последний аргумент может быть днями
        if args and args[-1].isdigit():
            days = int(args[-1])
            name = " ".join(args[:-1])
        else:
            days = 7
            name = " ".join(args)
            
        history = self.bot.collector.get_curator_history(name, days)
        if history:
            msg = f"**📈 История {name} ({days} дн.):**\n"
            for date, hour, count, _ in history[:10]:
                msg += f"- {date} {hour}:00: {count} чатов\n"
            await ctx.send(msg)
        else:
            await ctx.send(f"Нет данных для {name}.")

async def setup(bot):
    await bot.add_cog(Stats(bot))