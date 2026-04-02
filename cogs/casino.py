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

LOOT_TABLE: List[Dict[str, float | str]] = [
        {"item": "7️⃣", "chance_percent": 0.1},
        {"item": "👑", "chance_percent": 1.0},
        {"item": "💎", "chance_percent": 2.0},
        {"item": "🍌", "chance_percent": 6.0},
        {"item": "🍓", "chance_percent": 10.0},
        {"item": "🍎", "chance_percent": 15.0},
        {"item": "🍇", "chance_percent": 16.0},
        {"item": "🍋", "chance_percent": 20.0},
        {"item": "🍊", "chance_percent": 20.0},
        {"item": "🍒", "chance_percent": 9.9},
    ]

class CasinoCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "casino": self.cmd_casino
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

    def validate_loot_table(self, table: List[Dict[str, float | str]]) -> None:
        total = sum(float(entry["chance_percent"]) for entry in table)
        if round(total, 6) != 100.0:
            raise ValueError(f"Сумма шансов должна быть 100%, сейчас: {total}%")

    def roll_symbol(self, table: List[Dict[str, float | str]]) -> str:
        symbols = [str(entry["item"]) for entry in table]
        weights = [float(entry["chance_percent"]) for entry in table]
        return random.choices(symbols, weights=weights, k=1)[0]

    def get_jackpot_multiplier(self, symbol: str) -> int:
        """
        Возвращает множитель для тройного совпадения.
        """
        if symbol == "7️⃣":
            return 1000
        elif symbol == "💎":
            return 500
        elif symbol == "👑":
            return 100
        else:
            return 2

    def check_win(self, slot1: str, slot2: str, slot3: str, bet: int) -> Dict:
        """
        Проверяет результат спина и считает выплату.
        """
        comment = ""
        multiplier = 0

        # Тройные совпадения с разными джекпотами
        if slot1 == slot2 == slot3 == "7️⃣":
            comment = f"СУПЕРДЖЕКПОТ! НЕВЕРОЯТНО! Вам начислено pa1kaCoin {bet * 1000} монет 🎉"
            multiplier = 1000

        elif slot1 == slot2 == slot3 == "💎":
            comment = f"АЛМАЗНЫЙ ДЖЕКПОТ! ВОТ ЭТО УДАЧА! Вам начислено pa1kaCoin {bet * 500} монет 💎"
            multiplier = 500

        elif slot1 == slot2 == slot3 == "👑":
            comment = f"КОРОЛЕВСКИЙ СУПЕРДЖЕКПОТ, вам начислено pa1kaCoin {bet * 100}! 👑"
            multiplier = 100

        elif slot1 == slot2 == slot3:
            comment = f"ДЖЕКПОТ! Победитель по жизни, вам начислено pa1kaCoin {bet * 2} монет! 🍀"
            multiplier = 2

        # Любая пара
        elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
            comment = f"Утешительный приз, вам будет возвращена половина вашей ставки: pa1kaCoin {int(bet * 0.5)} монет! Хоть что-то 🙂"
            multiplier = 0.5

        # Ничего
        else:
            comment = "Ничего не совпало. Повезёт в следующий раз!"
            multiplier = 0

        payout = bet * multiplier
        profit = payout - bet

        return {
            "slot1": slot1,
            "slot2": slot2,
            "slot3": slot3,
            "comment": comment,
            "multiplier": multiplier,
            "bet": bet,
            "payout": payout,
            "profit": profit,
        }

    def spin_slots(self, bet: int, table: List[Dict[str, float | str]]) -> Dict:
        """
        Делает один спин из 3 барабанов.
        """
        if bet <= 0:
            raise ValueError("Ставка должна быть больше 0")

        slot1 = self.roll_symbol(table)
        slot2 = self.roll_symbol(table)
        slot3 = self.roll_symbol(table)

        return self.check_win(slot1, slot2, slot3, bet)

    async def cmd_casino(self, cmd):
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

        self.validate_loot_table(LOOT_TABLE)

        result = self.spin_slots(bet, LOOT_TABLE)

        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": -bet}})
        collection.update_one({"_id": cmd.user.id}, {"$inc": {"balance": int(bet * result["multiplier"])}})

        await cmd.reply(f"@{cmd.user.name}: {result['slot1']} {result['slot2']} {result['slot3']} - {result['comment']}")


def setup(bot):
    return CasinoCog(bot)