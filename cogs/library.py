import discord
from discord.ext import commands
from discord import app_commands
import logging

class Library(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Вспомогательный метод: Запрос к AI ---
    async def _process_fact_check(self, query: str) -> str:
        """
        Безопасно обращается к сервису RAG, который живет в bot.py
        """
        # Проверяем, существует ли сервис (не упал ли он при старте)
        if not hasattr(self.bot, 'rag_service') or self.bot.rag_service is None:
            logging.error("Попытка использования RAG, но сервис не инициализирован.")
            return "⚠️ Система поиска временно недоступна (ошибка инициализации AI на сервере)."

        # Обращаемся к сервису
        try:
            return await self.bot.rag_service.get_answer(query)
        except Exception as e:
            logging.error(f"Ошибка при запросе к RAG: {e}")
            return "⚠️ Произошла внутренняя ошибка нейросети."

    # --- Вспомогательный метод: Выбор цвета ---
    def _get_embed_color(self, text: str):
        """
        Определяет цвет полоски в зависимости от эмодзи в ответе
        """
        if "✅" in text: return discord.Color.green()   # Разрешено
        if "❌" in text: return discord.Color.red()     # Запрещено / Не найдено
        if "⚠️" in text: return discord.Color.gold()    # Предупреждение (матрицы)
        return discord.Color.blue()                     # Нейтральный

    # ====================================================
    # 1. Классическая команда (!fact текст)
    # ====================================================
    @commands.command(name='fact', aliases=['факт', 'check', 'проверь'])
    async def fact_prefix(self, ctx, *, query: str):
        """
        Проверяет теорему по базе ФПУ.
        Использование: !fact <вопрос>
        """
        # Показываем статус "Печатает...", пока AI думает
        async with ctx.typing():
            # Получаем текст от нейросети
            answer_text = await self._process_fact_check(query)
            
            # Собираем красивый Embed
            color = self._get_embed_color(answer_text)
            embed = discord.Embed(
                title="🔍 Проверка теоремы (ЕГЭ)",
                description=answer_text,
                color=color
            )
            embed.set_footer(text=f"Запрос от {ctx.author.display_name}: {query}")
        
        # Отправляем ответ (Reply)
        await ctx.reply(embed=embed)

    # Обработка ошибки, если пользователь не ввел текст
    @fact_prefix.error
    async def fact_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Вы не написали вопрос!\n\n**Пример:**\n`!fact Теорема Менелая`\n`!fact Можно ли использовать матрицы?`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    # ====================================================
    # 2. Слэш-команда (/fact текст)
    # ====================================================
    @app_commands.command(name="fact", description="Проверить, нужно ли доказывать теорему на ЕГЭ")
    @app_commands.describe(query="Формулировка теоремы или вопрос")
    async def fact_slash(self, interaction: discord.Interaction, query: str):
        # Discord требует ответ за 3 секунды. AI может думать дольше.
        # defer() пишет "Bot is thinking...", давая нам 15 минут времени.
        await interaction.response.defer(thinking=True)
        
        answer_text = await self._process_fact_check(query)
        color = self._get_embed_color(answer_text)
        
        embed = discord.Embed(
            title="🔍 Проверка теоремы",
            description=answer_text,
            color=color
        )
        # В слэш-командах footer с запросом не так важен, но можно оставить
        embed.set_footer(text=f"База знаний ФПУ • Запрос: {query}")
        
        # Отправляем через followup (так как мы делали defer)
        await interaction.followup.send(embed=embed)

# Функция загрузки кога
async def setup(bot):
    await bot.add_cog(Library(bot))