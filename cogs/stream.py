class StreamCog:
    def __init__(self, bot):
        self.bot = bot

    def get_commands(self):
        return {
            "stream": self.cmd_stream
        }

    async def cmd_stream(self, cmd):
        is_broadcaster = cmd.user.name.lower() == self.bot.CHANNEL_NAME.lower()
        is_moderator = cmd.user.mod

        if not (is_broadcaster or is_moderator):
            await cmd.reply("Не твоя кнопка.")
            return

        raw = (cmd.parameter or "").strip().lower()

        if not raw:
            status = "ON" if self.bot.is_streaming else "OFF"
            await cmd.reply(f"stream = {status}")
            return

        if raw == "on":
            self.bot.is_streaming = True
            print("STREAM FLAG MANUALLY SET TO: ON")
            await cmd.reply("stream mode: ON")
            return

        if raw == "off":
            self.bot.is_streaming = False
            print("STREAM FLAG MANUALLY SET TO: OFF")
            await cmd.reply("stream mode: OFF")
            return

        await cmd.reply("Используй: !stream on или !stream off")

def setup(bot):
    return StreamCog(bot)