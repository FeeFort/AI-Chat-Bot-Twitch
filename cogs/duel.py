import aiohttp
import asyncio
import os
import random
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class DuelCog:
    def __init__(self, bot):
        self.bot = bot
        self.active_duels = {}

    def get_commands(self):
        return {
            "duel": self.cmd_duel
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
            user = collection.insert_one({
                "_id": user_id,
                "balance": 0
            })

        return user

    async def create_duel(self, challenger_id, target_id, challenger_name, target_name, bet, cmd):
        """
        Создание дуэли и ожидание ответа target_id
        """
        if target_id in self.active_duels:
            await cmd.send(f"<@{challenger_name}>, {target_name} уже имеет активный вызов!")
            return

        duel = {
            "challenger": challenger_id,
            "target": target_id,
            "bet": bet,
            "task": None
        }
        self.active_duels[target_id] = duel

        await cmd.send(f"@{target_name}, вас вызвал @{challenger_name} на дуэль на {bet} монет! Чтобы принять — !duel accept, чтобы отказаться — !duel decline.")

        async def duel_timeout():
            await asyncio.sleep(30)
            if target_id in self.active_duels:
                self.active_duels.pop(target_id)
                await cmd.send(f"@{target_id} не ответил на вызов, дуэль отменена.")

        duel["task"] = asyncio.create_task(duel_timeout())

    async def handle_duel_response(self, user_id, message, cmd):
        """
        Обработка ответа пользователя на дуэль
        """
        if user_id not in self.active_duels.items():
            await cmd.reply("У вас нет активных дуэлей!")

        duel = self.active_duels[user_id]

        if message.lower() == "accept":
            duel["task"].cancel()
            self.active_duels.pop(user_id)

            winner = random.choice([duel["challenger"], duel["target"]])
            loser = duel["target"] if winner == duel["challenger"] else duel["challenger"]

            collection.update_one({"_id": winner}, {"$inc": {"balance": duel['bet'] * 2}})
            collection.update_one({"_id": loser}, {"$inc": {"balance": -duel['bet']}})

            await cmd.send(f"Дуэль! Победитель: @{winner}, он получает {duel['bet'] * 2} монет! ")

        elif message.lower() == "decline":
            duel["task"].cancel()
            self.active_duels.pop(user_id)
            await cmd.send(f"@{user_id} отклонил дуэль с @{duel['challenger']}.")
        else:
            await cmd.reply("Использование: !duet @тег [ставка] ИЛИ !duel accept/decline")
            return

    async def cmd_duel(self, cmd):
        parts = cmd.parameter.strip().split()

        if len(parts) == 0:
            await cmd.reply("Использование: !duet @тег [ставка] ИЛИ !duel accept/decline")
            return
        elif len(parts) == 1:
            await self.handle_duel_response(cmd.user.id, parts[0], cmd)
        else:
            target = parts[0].lstrip("@").lower()
            bet = int(parts[1])

            if bet < 100:
                await cmd.reply("Ставка не может быть меньше 100!")
                return

            target_id = await self.get_user_id_by_login(self.bot.CLIENT_ID, self.bot.APP_ACCESS_TOKEN, target)
            challenger_id = cmd.user.id

            target_user = await self.find_or_create_user(target_id)
            challenger_user = await self.find_or_create_user(challenger_id)

            if target_user['balance'] < bet:
                await cmd.reply("У вашего соперника недостаточно средств для дуэли!")
                return

            if challenger_user['balance'] < bet:
                await cmd.reply("У вас недостаточно средств!")
                return

            await self.create_duel(target_id, challenger_id, cmd.user.name, target, bet, cmd)

def setup(bot):
    return DuelCog(bot)