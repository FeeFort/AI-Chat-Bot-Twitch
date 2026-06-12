import random


class SexCog:
    def __init__(self, bot):
        self.bot = bot

        self.bad_phrases = [
            "Партнер уснул на середине",
            "Зашла мама с подносом еды",
            "Сказали: И это все?",
            "Свело ногу в самый важный момент",
            "Ты случайно назвал имя своей бывшей",
            "В комнату зашел дед и начал давать советы",
            "Оказалось, что это был сон",
            "Тебя стошнило от волнения",
            "Партнер попросил вернуть деньги за такси",
            "Вы решили просто поиграть в карты",
            "Ты проиграл в гляделки и расплакался",
        ]

        self.mid_phrases = [
            "Было неплохо, но в Валоранте ты стараешься больше",
            "Соседи просто постучали по батарее",
            "В носках было удобнее, чем без них",
            "Уложились ровно в 2 минуты",
            "Кот смотрел с легким осуждением",
            "Партнер поставил тебе 6 из 10",
            "Вы постоянно бились лбами",
            "Случайно упали с кровати, но продолжили на ковре",
        ]

        self.epic_phrases = [
            "Соседи вызвали ОМОН от криков",
            "Рекорд! Это было легендарно",
            "100/10, чат в шоке, Твич чуть не забанили",
            "Кровать рухнула в подвал к соседям",
            "Вы оба апнули Радианта после этого",
            "Об этом напишут в учебниках истории",
            "Партнер удалил Тиндер, потому что лучше уже не будет",
            "Это было так мощно, что у соседа выключился комп",
        ]

    def get_commands(self):
        return {
            "sex": self.cmd_sex
        }

    async def get_random_chatter(self, cmd) -> dict | None:
        chatters = await self.bot.get_chatters()
        ignored_logins = {
            self.bot.BOT_LOGIN.lower(),
            cmd.user.name.lower(),
        }

        candidates = [
            chatter for chatter in chatters
            if chatter["login"].lower() not in ignored_logins
        ]

        if not candidates:
            return None

        return random.choice(candidates)

    async def cmd_sex(self, cmd):
        sender = cmd.user.name.replace("@", "")
        param = cmd.parameter.strip()

        if param == "":
            try:
                random_chatter = await self.get_random_chatter(cmd)
            except Exception:
                await cmd.reply("Не удалось получить список пользователей чата.")
                return

            if random_chatter is None:
                await cmd.reply("Сейчас в чате нет подходящих пользователей для выбора.")
                return

            target = random_chatter["login"]
        else:
            target = param

        target = target.replace("@", "").strip()
        sender_lower = sender.lower()
        target_lower = target.lower()

        if target_lower == sender_lower:
            await cmd.reply(
                f"@{sender} решил никого не искать и уединился со своей правой рукой... Итог: 10/10, скилл растет, ни от кого не зависишь!"
            )
            return

        if target_lower == "pa1ka":
            await cmd.reply(
                f"Стоп, @{sender}! @{target} женат на @ouyumeko, так что ловить нечего. Иди ищи другую цель, например @akakiryuuu!"
            )
            return

        if target_lower == "akakiryuuu":
            await cmd.reply(
                f"@{sender} и @{target} зашли в комнату, но @{target} зафонился и у него даже не встал. Это был самый позорный опыт в твоей жизни."
            )
            return

        power = random.randint(0, 100)

        if power <= 30:
            result = random.choice(self.bad_phrases)
        elif power <= 80:
            result = random.choice(self.mid_phrases)
        else:
            result = random.choice(self.epic_phrases)

        await cmd.reply(
            f"@{sender} и @{target} уединились! Мощность процесса: {power}%. Результат: {result}."
        )


def setup(bot):
    return SexCog(bot)
