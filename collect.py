import re
from datetime import datetime, timedelta, timezone
from users import user_map
import logging
from utils import Time_to_send, Default_curator

async def collect_discord_data(channel, black_users):
    """Собирает сообщения пользователей за последний час с группировкой по часу"""

    def get_curator_chats(message):
         # Время сообщения, если это 18:45 то количество чатов за 17, если 18:50 то за 18
         # Прибавляем поскольку считаем время относительно
        if (message.created_at.minute < Time_to_send):
            msg_time = message.created_at + timedelta(hours=2)
        else:
            msg_time = message.created_at + timedelta(hours=3)

         # Список месяцев в родительном падеже
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        
        day = msg_time.day
        month_name = months[msg_time.month - 1]
        hour = msg_time.hour

        numbers = re.findall(r'\d+', message.content.strip())
        if numbers:
            total = sum(map(int, numbers))
        return total, day, month_name, hour

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    curator_data = {}
    seen_users = set()

    day = month_name = hour = None

    async for message in channel.history(limit=1000):
        if message.author.bot:
            if message.content.startswith("Пишите количество чатов за"):
                break
            continue
        if message.created_at < one_hour_ago:
            break
        author_tag = str(message.author)
        if author_tag in seen_users:
            continue  # Уже считан
        
        name = user_map.get(author_tag, -1)

        if (name == -1) and (name not in black_users):
             # Отправляем сообщение в канал
            warning_msg = f"Пользователь {message.author.mention} не найден в базе кураторов!"
            await channel.send(warning_msg)
            
            # Логируем в консоль
            logging.info(f"Пользователь {author_tag} не является куратором")
            black_users.add(name)

            # Если неизвестный куратор - Егор Гаязов
            total, day, month_name, hour = get_curator_chats(message)
            curator_data[Default_curator] = total
            seen_users.add(author_tag)
            logging.info(f"Считали Дефолтного куратора - {Default_curator} [{day} {month_name}] [{hour}:00]: {total} чатов")

            continue
        elif (name == -1):
            # Логируем в консоль
            logging.info(f"Пользователь {author_tag} не является куратором")

             # Если неизвестный куратор - Егор Гаязов
            total, day, month_name, hour = get_curator_chats(message)
            curator_data[Default_curator] = total
            seen_users.add(author_tag)
            logging.info(f"Считали Дефолтного куратора - {Default_curator} [{day} {month_name}] [{hour}:00]: {total} чатов")
            continue
        
        total, day, month_name, hour = get_curator_chats(message)
        curator_data[name] = total
        seen_users.add(author_tag)
        logging.info(f"Считали - {name} [{day} {month_name}] [{hour}:00]: {total} чатов")
    return curator_data, hour, day, month_name
