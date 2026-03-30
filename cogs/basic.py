class BasicCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "ping": self.cmd_ping
        }

    async def cmd_ping(self, cmd):
        await cmd.reply("Pong!")

def setup(bot):
    return BasicCog(bot)