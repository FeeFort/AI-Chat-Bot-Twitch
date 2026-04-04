class HelpCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "help": self.cmd_help
        }

    async def cmd_help(self, cmd):
        await cmd.reply("Ознакомиться со списком команд: https://feefort.github.io")

def setup(bot):
    return HelpCog(bot)