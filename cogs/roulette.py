import os
import aiohttp
from pymongo import MongoClient
import random
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class RouletteCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "roulette": self.cmd_roulette
        }

    async def find_or_create_user(self, user_id):
        user = collection.find_one({"_id": user_id})
        if user is None:
            collection.insert_one({
                "_id": user_id,
                "balance": 0
            })

    async def cmd_roulette(self, cmd):
        parts = cmd.parameter.strip().split()
        if len(parts) == 0:
            await cmd.reply("Использование: !casino [ставка]")
            return

        bet = int(parts[0])

        if bet < 100:
            await cmd.reply("Ставка не может быть меньше 100!")
            return

        await self.find_or_create_user(cmd.user.id)

        user = collection.find_one({"_id": cmd.user.id})
        if user["balance"] < bet:
            await cmd.reply("У вас недостаточно средств!")
            return

        roulette = [1, 2, 3, 4, 5, 6]
        roll_expect = random.choice(roulette)
        roll = random.choice(roulette)

        if roll_expect == roll:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": bet}})
            await cmd.reply(f"Рулетка сыграла, победа! Вам начислено pa1kaCoin {bet * 2} монет.")
        else:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": -bet}})
            await cmd.reply(f"Рулетка не сыграла.")

def setup(bot):
    return RouletteCog(bot)