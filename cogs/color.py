import os
from pymongo import MongoClient
import random
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

class ColorCog:
    def __init__(self, bot):
        self.bot = bot
        self.colors = [
            "white",
            "black",
            "red",
            "blue",
            "orange",
            "yellow",
            "green",
            "purple",
            "brown"
        ]
        self.colors_info = {
            "white": {"ru": "Белый", "emoji": "⚪"},
            "black": {"ru": "Чёрный", "emoji": "⚫"},
            "red": {"ru": "Красный", "emoji": "🔴"},
            "blue": {"ru": "Синий", "emoji": "🔵"},
            "orange": {"ru": "Оранжевый", "emoji": "🟠"},
            "yellow": {"ru": "Жёлтый", "emoji": "🟡"},
            "green": {"ru": "Зелёный", "emoji": "🟢"},
            "purple": {"ru": "Фиолетовый", "emoji": "🟣"},
            "brown": {"ru": "Коричневый", "emoji": "🟤"},
        }

    def get_commands(self):
        return {
            "color": self.cmd_color
        }

    async def find_or_create_user(self, user_id):
        user = collection.find_one({"_id": user_id})
        if user is None:
            collection.insert_one({
                "_id": user_id,
                "balance": 0
            })

    async def cmd_color(self, cmd):
        parts = cmd.parameter.strip().split()
        if len(parts) == 0:
            await cmd.reply("Использование: !color [ставка] [цвет]")
            return

        bet = int(parts[0])
        color_excepted = parts[1]

        if bet < 100:
            await cmd.reply("Ставка не может быть меньше 100!")
            return

        await self.find_or_create_user(cmd.user.id)

        user = collection.find_one({"_id": cmd.user.id})
        if user["balance"] < bet:
            await cmd.reply("У вас недостаточно средств!")
            return

        color = random.choice(self.colors)

        if color == color_excepted:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": int(bet * 0.5)}})
            await cmd.reply(f"Выпал {self.colors_info[color]["emoji"]} {self.colors_info[color]["ru"]}. Вам начислено pa1kaCoin {int(bet * 1.5)} монет.")
        else:
            collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": -bet}})
            await cmd.reply(f"Выпал {self.colors_info[color]["emoji"]} {self.colors_info[color]["ru"]}. Цвет не угадан.")

        await cmd.reply("")

def setup(bot):
    return ColorCog(bot)