import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
import math
from huggingface_hub import AsyncInferenceClient
from resources import KNOWLEDGE_BASE, MATH_FACTS

class Library(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hf_token = os.getenv("HF_TOKEN")
        self.model_id = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        
        if self.hf_token:
            self.client = AsyncInferenceClient(token=self.hf_token)
        else:
            self.client = None
            logging.warning("⚠️ HF_TOKEN не найден. Поиск работать не будет.")

    def calculate_cosine_similarity(self, v1, v2):
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if magnitude1 == 0 or magnitude2 == 0: return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def mean_pooling(self, embedding_result):
        if isinstance(embedding_result[0], list):
            dim = len(embedding_result[0])
            avg = [0.0] * dim
            for token_vec in embedding_result:
                for i, val in enumerate(token_vec):
                    avg[i] += val
            return [x / len(embedding_result) for x in avg]
        return embedding_result

    async def _get_embeddings_search(self, query, database):
        """Гибридный поиск: Сначала слова, потом нейросеть"""
        
        # 1. Поиск по ключевым словам (KW Search) - Приоритет №1
        kw_results = []
        query_lower = query.lower().strip()
        
        for item in database:
            # Безопасное получение полей
            title = item.get('title', '').lower()
            tags = item.get('tags', '').lower()
            
            # Точное вхождение фразы в название (Вес: 1.5)
            if query_lower in title:
                kw_results.append((1.5, item))
            # Вхождение в теги (Вес: 1.2)
            elif query_lower in tags:
                kw_results.append((1.2, item))

        # 2. AI Поиск (Semantic Search) - Приоритет №2
        ai_results = []
        try:
            # Отправляем батч текстов в нейросеть
            texts_to_embed = [query] + [item['title'] for item in database]
            embeddings = await self.client.feature_extraction(text=texts_to_embed, model=self.model_id)
            
            # Проверяем, не побила ли API результаты (бывает на бесплатном тарифе)
            if len(embeddings) == len(texts_to_embed):
                query_vector = self.mean_pooling(embeddings[0])
                doc_vectors = embeddings[1:]
                
                for idx, doc_vec in enumerate(doc_vectors):
                    d_vec_pooled = self.mean_pooling(doc_vec)
                    score = self.calculate_cosine_similarity(query_vector, d_vec_pooled)
                    ai_results.append((score, database[idx]))
            else:
                logging.warning(f"AI API вернул неполный список векторов ({len(embeddings)}/{len(texts_to_embed)})")
                
        except Exception as e:
            logging.error(f"AI Search Error: {e}")

        # 3. Умное объединение
        # Создаем карту results, где ключ - название факта. 
        # Если факт найден и по словам, и по AI - берем максимальный балл.
        final_map = {}
        
        for score, item in ai_results:
            final_map[item['title']] = (score, item)
            
        for score, item in kw_results:
            # Результат по словам перезаписывает AI, так как score > 1.0 (а у AI макс 1.0)
            final_map[item['title']] = (score, item)
            
        # Превращаем обратно в список и сортируем
        final_results = list(final_map.values())
        final_results.sort(key=lambda x: x[0], reverse=True)
        
        return final_results

    async def _create_materials_embed(self, query):
        results = await self._get_embeddings_search(query, KNOWLEDGE_BASE)
        top_5 = results[:5]

        embed = discord.Embed(title=f"📚 Материалы: {query}", color=discord.Color.blue())
        found_any = False
        for score, item in top_5:
            if score < 0.25: continue # Фильтр мусора
            found_any = True
            embed.add_field(name=item['title'], value=f"[Скачать]({item['url']})", inline=False)
        
        if not found_any:
             embed.description = "Ничего похожего не найдено."
             embed.set_footer(text="Попробуйте перефразировать запрос.")
        
        return embed

    async def _create_fact_embed(self, query):
        results = await self._get_embeddings_search(query, MATH_FACTS)
        
        if not results:
             return discord.Embed(title="Ошибка", description="База фактов пуста или недоступна.", color=discord.Color.red())

        best_score, best_fact = results[0]
        
        embed = discord.Embed(title=f"🔍 Факт: {query}", color=discord.Color.green())
        
        # Если даже лучшее совпадение слишком слабое (меньше 30%)
        if best_score < 0.5:
            embed.color = discord.Color.red()
            embed.description = f"🤷‍♂️ Не нашел факта **«{query}»** в перечне."
            # Показать, что бот думал, чтобы понять логику (для отладки можно убрать)
            embed.set_footer(text=f"Ближайшее, что нашел: {best_fact['title']} (Совпадение: {int(best_score*100)}%)")
        else:
            embed.title = f"📖 {best_fact['title']}"
            if best_fact['type'] == 'theory':
                status = "✅ **МОЖНО ИСПОЛЬЗОВАТЬ**"
                desc = "Есть в теории учебника ФПУ."
                embed.color = discord.Color.green()
            if best_fact['type'] == 'task':
                status = "✅ **МОЖНО ИСПОЛЬЗОВАТЬ**"
                desc = "Есть в учебнике в качестве задачи."
                embed.color = discord.Color.green()
            elif best_fact['type'] == 'forbidden':
                status = "⚠️ **ЛУЧШЕ ДОКАЗАТЬ**"
                desc = "В учебнике это задача. На ЕГЭ лучше сослаться (Задача №...) или доказать."
                embed.color = discord.Color.gold()
            elif best_fact['type'] == 'forbidden':
                status = "⛔ **НЕЛЬЗЯ**"
                desc = "Нет в школьной программе. Опасно использовать."
                embed.color = discord.Color.dark_red()
            
            embed.add_field(name="Вердикт", value=status, inline=False)
            embed.add_field(name="Источник", value=f"`{best_fact['source']}`", inline=False)
            embed.set_footer(text=desc)
        
        return embed

    # --- СЛЭШ КОМАНДЫ ---
    @app_commands.command(name="материалы", description="Найти теорию (умный поиск)")
    async def slash_materials(self, interaction: discord.Interaction, query: str):
        if not self.client:
            await interaction.response.send_message("❌ Нет токена HF.", ephemeral=True)
            return
        await interaction.response.defer()
        embed = await self._create_materials_embed(query)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="факт", description="Проверить факт для ЕГЭ")
    async def slash_fact(self, interaction: discord.Interaction, query: str):
        if not self.client:
            await interaction.response.send_message("❌ Нет токена HF.", ephemeral=True)
            return
        await interaction.response.defer()
        embed = await self._create_fact_embed(query)
        await interaction.followup.send(embed=embed)

    # --- ТЕКСТОВЫЕ КОМАНДЫ (!) ---
    @commands.command(name="материалы")
    async def text_materials(self, ctx, *, query: str = None):
        if not query:
            await ctx.send("❌ Укажите запрос: `!материалы [тема]`")
            return
        if not self.client:
            await ctx.send("❌ Нет токена HF.")
            return
        async with ctx.typing():
            embed = await self._create_materials_embed(query)
            await ctx.send(embed=embed)

    @commands.command(name="факт")
    async def text_fact(self, ctx, *, query: str = None):
        if not query:
            await ctx.send("❌ Укажите факт: `!факт [название]`")
            return
        if not self.client:
            await ctx.send("❌ Нет токена HF.")
            return
        async with ctx.typing():
            embed = await self._create_fact_embed(query)
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Library(bot))