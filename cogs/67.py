class SIX_SEVEN_Cog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "67": self.cmd_67
        }

    async def cmd_67(self, cmd):
        await cmd.reply("six seven")
        await cmd.reply("сикс севен")
        await cmd.reply("67")

def setup(bot):
    return SIX_SEVEN_Cog(bot)