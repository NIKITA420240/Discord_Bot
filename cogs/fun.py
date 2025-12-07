import discord
from discord.ext import commands
import os
import logging
from huggingface_hub import AsyncInferenceClient

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Получаем токен из .env
        self.hf_token = os.getenv("HF_TOKEN")
        
        # Инициализируем клиента Hugging Face
        # Если токена нет, клиент не создастся, и мы обработаем это в команде
        if self.hf_token:
            self.hf_client = AsyncInferenceClient(token=self.hf_token)
        else:
            self.hf_client = None
            logging.warning("⚠️ HF_TOKEN не найден в .env. Команда !анекдот работать не будет.")

        # Модель. Можно менять на:
        # - "Qwen/Qwen2.5-72B-Instruct" (Умная, но может быть медленной)
        # - "mistralai/Mistral-7B-Instruct-v0.3" (Быстрее)
        self.model_id = "Qwen/Qwen2.5-72B-Instruct"

    @commands.command(name="анекдот")
    async def анекдот(self, ctx):
        """Рассказывает анекдот, сгенерированный нейросетью"""
        
        if not self.hf_client:
            await ctx.send("❌ Настройка бота не завершена: отсутствует токен Hugging Face.")
            return

        # Отправляем сообщение "печатаю...", чтобы пользователь видел реакцию
        status_msg = await ctx.send("🤖 *Роюсь в базе данных юмора...*")

        try:
            # Формируем промпт (запрос)
            messages = [
                {
                    "role": "system", 
                    "content": "Ты — стендап-комик. Расскажи короткий, свежий и смешной анекдот на русском языке. Избегай старых бородатых шуток."
                },
                {
                    "role": "user", 
                    "content": "Рассмеши меня."
                }
            ]

            # Делаем запрос к API
            response = await self.hf_client.chat_completion(
                messages=messages,
                model=self.model_id,
                max_tokens=250,  # Ограничение длины
                temperature=0.85 # Креативность
            )
            
            joke_text = response.choices[0].message.content
            
            # Редактируем сообщение, вставляя результат
            await status_msg.edit(content=f"🎭 **Анекдот от нейросети:**\n\n{joke_text}")

        except Exception as e:
            logging.error(f"Ошибка нейросети: {e}")
            await status_msg.edit(content="🤯 У нейросети творческий кризис (ошибка API). Попробуйте позже.")

async def setup(bot):
    await bot.add_cog(Fun(bot))