import os
import aiohttp
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class TransferCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "pay": self.cmd_pay
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

    async def cmd_pay(self, cmd):
        parts = cmd.parameter.strip().split()

        if len(parts) != 2:
            await cmd.reply("Использование: !pay [@тег] [кол-во]")
            return

        target_login = parts[0].lstrip("@").lower()
        amount = int(parts[1])

        target_user_id = await self.get_user_id_by_login(self.bot.CLIENT_ID, self.bot.APP_ACCESS_TOKEN, target_login)
        if target_user_id is None:
            await cmd.reply("Пользователь не найден")
            return

        await self.find_or_create_user(target_user_id)
        await self.find_or_create_user(cmd.user.id)

        user = collection.find_one({"_id": cmd.user.id})
        if user["balance"] < amount:
            await cmd.reply("У вас недостаточно средств!")
            return

        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": -amount}})
        collection.update_one({"_id": target_user_id}, {"$inc": {"balance": amount}})
        await cmd.reply(f"Вы успешно перевели @{target_login} pa1kaCoin {amount} монет.")

def setup(bot):
    return TransferCog(bot)