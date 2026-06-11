import os
import aiohttp
from pymongo import MongoClient
import random
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class BlackjackCog:
    def __init__(self, bot):
        self.bot = bot
        # Теперь здесь все карты от 2 до Туза
        self.ranks = {
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, 
            "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10, "A": 11
        }
        self.suits = ['♥️', '♦️', '♠️', '♣️']

    def get_full_deck(self):
        deck = []
        for suit in self.suits:
            for rank, value in self.ranks.items():
                deck.append({"rank": rank, "value": value, "suit": suit})
        return deck
    
    def calculate_hand_value(self, hand):
        value = sum(card["value"] for card in hand)
        # Считаем количество тузов в руке
        aces = sum(1 for card in hand if card["rank"] == "A")
        
        # Пока сумма > 21 и есть тузы, которые считаются за 11 -> превращаем их в 1
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        return value

    def get_commands(self):
        return {
            "blackjack": self.cmd_blackjack
        }

    async def get_user_id_by_login(self, client_id: str, access_token: str, login: str) -> str | None:
        url = "https://api.twitch.tv/helix/users"
        headers = {
            "Client-Id": client_id,
            "Authorization": f"Bearer {access_token}",
        }
        params = {
            "login": login,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                resp.raise_for_status()
                payload = await resp.json()

                data = payload.get("data", [])
                if not data:
                    return None

                return data[0]["id"]

    async def find_or_create_user(self, user_id):
        user = collection.find_one({"_id": user_id})
        if user is None:
            collection.insert_one({
                "_id": user_id,
                "balance": 0
            })

    async def cmd_blackjack(self, cmd):
        parts = cmd.parameter.strip().split()
        if len(parts) == 0:
            await cmd.reply("Использование: !blackjack [ставка]")
            return

        try:
            bet = int(parts[0])
        except ValueError:
            await cmd.reply("Ставка должна быть числом!")
            return

        if bet < 100:
            await cmd.reply("Ставка не может быть меньше 100!")
            return

        await self.find_or_create_user(cmd.user.id)

        user = collection.find_one({"_id": cmd.user.id})
        if user["balance"] < bet:
            await cmd.reply("У вас недостаточно средств!")
            return

        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": -bet}})

        # Создаем колоду
        deck = self.get_full_deck()
        random.shuffle(deck)

        # Берем карты
        card1bot, card2bot = deck.pop(), deck.pop()
        card1user, card2user = deck.pop(), deck.pop()

        # Собираем карты в списки
        hand_bot = [card1bot, card2bot]
        hand_user = [card1user, card2user]

        # Считаем суммы через новую функцию
        sumBot = self.calculate_hand_value(hand_bot)
        sumUser = self.calculate_hand_value(hand_user)

        # Исправленная функция проверки
        def is_blackjack(c1, c2):
            return (c1["rank"] == "A" and c2["value"] == 10) or \
                   (c2["rank"] == "A" and c1["value"] == 10)

        bot_blackjack = is_blackjack(card1bot, card2bot)
        user_blackjack = is_blackjack(card1user, card2user)

        # Исправленный вывод (обращаемся к ["rank"])
        result_text = (
            f"Сумма бота: {sumBot} (карты {card1bot['rank']}{card1bot['suit']} {card2bot['rank']}{card2bot['suit']}). "
            f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user['rank']}{card1user['suit']} {card2user['rank']}{card2user['suit']})."
        )

        # 1. Оба перебрали
        if sumBot > 21 and sumUser > 21:
            await cmd.reply(f"Оба проиграли. {result_text}")
            return

        # 2. Бот перебрал
        if sumBot > 21 and sumUser <= 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet * 2}})
            await cmd.reply(
                f"Бот перебрал! @{cmd.user.name} выиграл! "
                f"Выигрыш: pa1kaCoin {bet * 2}. {result_text}"
            )
            return

        # 3. Пользователь перебрал
        if sumUser > 21 and sumBot <= 21:
            await cmd.reply(f"@{cmd.user.name} перебрал. Бот выиграл. {result_text}")
            return

        # 4. Оба BLACKJACK
        if bot_blackjack and user_blackjack:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
            await cmd.reply(
                f"У обоих BLACKJACK! Ставка pa1kaCoin {bet} возвращена на баланс. {result_text}"
            )
            return

        # 5. BLACKJACK у бота
        if bot_blackjack and not user_blackjack:
            await cmd.reply(f"Бот выбил BLACKJACK. {result_text}")
            return

        # 6. BLACKJACK у пользователя
        if user_blackjack and not bot_blackjack:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet * 3}})
            await cmd.reply(
                f"@{cmd.user.name} выбил BLACKJACK! "
                f"Выигрыш: pa1kaCoin {bet * 3}. {result_text}"
            )
            return

        # 7. Оба просто 21
        if sumBot == 21 and sumUser == 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
            await cmd.reply(
                f"Оба выбили 21. Ставка pa1kaCoin {bet} возвращена на баланс. {result_text}"
            )
            return

        # 8. Просто 21 у бота
        if sumBot == 21 and sumUser != 21:
            await cmd.reply(f"Бот выбил 21. {result_text}")
            return

        # 9. Просто 21 у пользователя
        if sumUser == 21 and sumBot != 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet * 3}})
            await cmd.reply(
                f"@{cmd.user.name} выбил 21! "
                f"Выигрыш: pa1kaCoin {bet * 3}. {result_text}"
            )
            return

        # 10. Обычная победа по сумме
        if sumBot > sumUser:
            await cmd.reply(f"Бот выиграл. {result_text}")
            return

        if sumUser > sumBot:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet * 2}})
            await cmd.reply(
                f"@{cmd.user.name} выиграл! "
                f"Выигрыш: pa1kaCoin {bet * 2}. {result_text}"
            )
            return

        # 11. Ничья
        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
        await cmd.reply(
            f"Ничья! Ставка pa1kaCoin {bet} возвращена на баланс. {result_text}"
        )


def setup(bot):
    return BlackjackCog(bot)