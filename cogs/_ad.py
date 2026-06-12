class AdCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "fp": self.cmd_fp,
            "funpay": self.cmd_funpay,
            "tg": self.cmd_tg,
        }

    async def cmd_fp(self, cmd):
        await cmd.send("Лучшие цены на цифровые товары и VP - на FunPay: https://funpay.com/go/pa1ka Покупая по ссылке, вы очень помогаете мне. Спасибо! :3 мяу...... ^_^")

    async def cmd_funpay(self, cmd):
        await cmd.send("🔥 Сэкономь на скинах! Дешевые VP: https://funpay.com/go/pa1ka | Steam без лишних переплат: https://funpay.com/go/pa1kaSteam Спасибо, что закупаетесь через меня - с каждой вашей покупки канал становится лучше! Респект вам!!!!")

    async def cmd_tg(self, cmd):
        parts = cmd.parameter.strip().split()

        if len(parts) == 0:
            await cmd.send("tg: https://t.me/pa1ka")
        else:
            count = int(parts[0])

            for _ in range(count):
                await cmd.send("tg: https://t.me/pa1ka")

def setup(bot):
    return AdCog(bot)