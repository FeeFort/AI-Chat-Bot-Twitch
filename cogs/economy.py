import aiohttp
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class EconomyCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "coins": self.cmd_coins,
            "balance": self.cmd_balance
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

    async def cmd_coins(self, cmd):
        is_broadcaster = cmd.user.name.lower() == self.bot.CHANNEL_NAME.lower()
        is_creator = cmd.user.id == "609907557"

        if not (is_broadcaster or is_creator):
            await cmd.reply("Не твоя кнопка.")
            return

        parts = cmd.parameter.strip().split()

        action = parts[0].lower()  # add / remove
        target_login = parts[1].lstrip("@").lower()
        amount = int(parts[2])

        target_user_id = await self.get_user_id_by_login(self.bot.CLIENT_ID, self.bot.APP_ACCESS_TOKEN, target_login)
        if target_user_id is None:
            await cmd.reply("Пользователь не найден")
            return

        await self.find_or_create_user(target_user_id)

        if action == "add":
            collection.update_one({"_id": target_user_id}, {"$inc": {"balance": amount}})
            await cmd.reply(f"Пользователю @{target_login} начислено {amount} монет.")
        elif action == "remove":
            collection.update_one({"_id": target_user_id}, {"$inc": {"balance": -amount}})
            await cmd.reply(f"У пользователя @{target_login} снято {amount} монет.")

    async def cmd_balance(self, cmd):
        await self.find_or_create_user(cmd.user.id)
        user = collection.find_one({"_id": cmd.user.id})
        await cmd.reply(f"@{cmd.user.name}, ваш баланс: {user["balance"]} монет.")


def setup(bot):
    return EconomyCog(bot)