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
        self.cards_list = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.cards = {
            "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10, "A": 11
        }

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

        card1bot = random.choice(self.cards_list)
        card2bot = random.choice(self.cards_list)
        card1user = random.choice(self.cards_list)
        card2user = random.choice(self.cards_list)

        sumBot = self.cards[card1bot] + self.cards[card2bot]
        sumUser = self.cards[card1user] + self.cards[card2user]

        # 1. Оба перебрали
        if sumBot > 21 and sumUser > 21:
            await cmd.reply(
                f"Оба проиграли. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма пользователя: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 2. Бот перебрал
        if sumBot > 21 and sumUser <= 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": int(bet * 3)}})
            await cmd.reply(
                f"Бот перебрал! @{cmd.user.name} выиграл! "
                f"Выигрыш: pa1kaCoin {bet * 3} монет. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 3. Пользователь перебрал
        if sumUser > 21 and sumBot <= 21:
            await cmd.reply(
                f"@{cmd.user.name} перебрал. Бот выиграл. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 4. Оба выбили 21
        if sumBot == 21 and sumUser == 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
            await cmd.reply(
                f"Оба выбили BLACKJACK! Ставка pa1kaCoin {bet} возвращена на баланс. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 5. Бот выбил 21
        if sumBot == 21 and sumUser != 21:
            await cmd.reply(
                f"Бот выбил BLACKJACK. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 6. Пользователь выбил 21
        if sumUser == 21 and sumBot != 21:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": int(bet * 5)}})
            await cmd.reply(
                f"@{cmd.user.name} выбил BLACKJACK! "
                f"Выигрыш: pa1kaCoin {bet * 5} монет. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 7. Обычное сравнение сумм
        if sumBot > sumUser:
            await cmd.reply(
                f"Бот выиграл. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        if sumUser > sumBot:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": int(bet * 3)}})
            await cmd.reply(
                f"@{cmd.user.name} выиграл! "
                f"Выигрыш: pa1kaCoin {bet * 3} монет. "
                f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
                f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
            )
            return

        # 8. Ничья
        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
        await cmd.reply(
            f"Ничья! Ставка pa1kaCoin {bet} возвращена на баланс. "
            f"Сумма бота: {sumBot} (карты {card1bot} {card2bot}). "
            f"Сумма @{cmd.user.name}: {sumUser} (карты {card1user} {card2user})."
        )


def setup(bot):
    return BlackjackCog(bot)