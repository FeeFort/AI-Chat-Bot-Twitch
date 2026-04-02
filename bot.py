# =========================================================
# imports
# =========================================================

import os
import asyncio
import re
import importlib
from collections import deque
from datetime import datetime

import aiohttp
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first

from get_response import getAiResponse
from pymongo import MongoClient

# =========================================================
# env/config
# =========================================================

load_dotenv()

USER_SCOPE = [
    AuthScope.USER_BOT,
    AuthScope.USER_READ_CHAT,
    AuthScope.USER_WRITE_CHAT,
]

BROADCASTER_SCOPE = [
    AuthScope.CHANNEL_READ_REDEMPTIONS,
    AuthScope.CHANNEL_MANAGE_REDEMPTIONS
]

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)

db = client["pa1ka"]
collection = db["Economy"]

print("Подключение успешно")

# =========================================================
# compatibility classes
# =========================================================

class _CompatChatRoom:
    def __init__(self, name: str):
        self.name = name


class _CompatChatUser:
    def __init__(self, user_id: str, name: str, mod: bool = False):
        self.id = user_id
        self.name = name
        self.mod = mod


# =========================================================
# chat entity classes
# =========================================================

class ChatMessage:
    def __init__(
        self,
        bot,
        twitch: Twitch,
        broadcaster_id: str,
        sender_id: str,
        room_name: str,
        user_id: str,
        user_name: str,
        text: str,
        message_id: str | None = None,
        reply_parent_msg_id: str | None = None,
        reply_parent_msg_body: str | None = None,
        reply_parent_user_login: str | None = None,
        user_mod: bool = False,
    ):
        self.bot = bot
        self._twitch = twitch
        self._broadcaster_id = broadcaster_id
        self._sender_id = sender_id

        self.room = _CompatChatRoom(room_name)
        self.user = _CompatChatUser(user_id=user_id, name=user_name, mod=user_mod)

        self.text = text
        self.id = message_id

        self.reply_parent_msg_id = reply_parent_msg_id
        self.reply_parent_msg_body = reply_parent_msg_body
        self.reply_parent_user_login = reply_parent_user_login

    async def reply(self, text: str):
        await self.bot.send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
            reply_parent_message_id=self.id,
        )

    async def send(self, text: str):
        await self.bot.send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
        )


class ChatCommand:
    def __init__(
        self,
        bot,
        twitch: Twitch,
        broadcaster_id: str,
        sender_id: str,
        user_id: str,
        user_name: str,
        parameter: str,
        message_id: str | None = None,
        reply_parent_msg_id: str | None = None,
        reply_parent_msg_body: str | None = None,
        reply_parent_user_login: str | None = None,
        user_mod: bool = False,
    ):
        self.bot = bot
        self._twitch = twitch
        self._broadcaster_id = broadcaster_id
        self._sender_id = sender_id

        self.user = _CompatChatUser(user_id=user_id, name=user_name, mod=user_mod)
        self.parameter = parameter

        self.id = message_id
        self.reply_parent_msg_id = reply_parent_msg_id
        self.reply_parent_msg_body = reply_parent_msg_body
        self.reply_parent_user_login = reply_parent_user_login

    async def reply(self, text: str):
        await self.bot.send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
            reply_parent_message_id=self.id,
        )

    async def send(self, text: str):
        await self.bot.send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
        )


# =========================================================
# bot class
# =========================================================

class Bot:
    # =====================================================
    # init/config
    # =====================================================

    def __init__(self):
        self.CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
        self.CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
        self.CHANNEL_NAME = os.getenv("TWITCH_CHANNEL_NAME")
        self.TOKEN = os.getenv("TWITCH_USER_ACCESS_TOKEN")
        self.REFRESH_TOKEN = os.getenv("TWITCH_USER_REFRESH_TOKEN")

        self.BROADCASTER_CLIENT_ID = os.getenv("BROADCASTER_CLIENT_ID")
        self.BROADCASTER_CLIENT_SECRET = os.getenv("BROADCASTER_CLIENT_SECRET")
        self.BROADCASTER_TOKEN = os.getenv("BROADCASTER_USER_ACCESS_TOKEN")
        self.BROADCASTER_REFRESH_TOKEN = os.getenv("BROADCASTER_USER_REFRESH_TOKEN")

        self.cogs = []
        self.commands = {}
        self.is_streaming = False
        self.MAX_HISTORY = 100
        self.CHAT_HISTORY = deque(maxlen=self.MAX_HISTORY)

        self.BOT_LOGIN = "pa1kamod"

        self.MENTION_PATTERN = re.compile(
            rf"(?<!\w)@?{re.escape(self.BOT_LOGIN)}(?!\w)",
            re.IGNORECASE,
        )
        self.MENTION_RE = re.compile(r"^@?([a-zA-Z0-9_]{4,25})(?:\s+(.*))?$")

        self.TWITCH_APP = None
        self.TWITCH_BROADCASTER_APP = None
        self.BROADCASTER_ID = None
        self.BOT_USER_ID = None
        self.APP_ACCESS_TOKEN = None

    # =====================================================
    # cog management
    # =====================================================

    def add_cog(self, cog):
        self.cogs.append(cog)
        self.commands.update(cog.get_commands())

    def load_extension(self, module_name: str):
        module = importlib.import_module(f"cogs.{module_name}")

        if not hasattr(module, "setup"):
            raise RuntimeError(f"{module_name} does not have setup(bot)")

        cog = module.setup(self)
        self.add_cog(cog)
        print(f"{module_name} loaded successfully!")

    # =====================================================
    # Twitch API helpers
    # =====================================================

    async def get_app_access_token(self) -> str:
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "grant_type": "client_credentials",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                resp.raise_for_status()
                payload = await resp.json()
                return payload["access_token"]

    async def send_chat_message_api(
        self,
        broadcaster_id: str,
        sender_id: str,
        message: str,
        reply_parent_message_id: str | None = None,
    ):
        if self.APP_ACCESS_TOKEN is None:
            self.APP_ACCESS_TOKEN = await self.get_app_access_token()

        url = "https://api.twitch.tv/helix/chat/messages"

        body = {
            "broadcaster_id": broadcaster_id,
            "sender_id": sender_id,
            "message": message,
        }

        if reply_parent_message_id:
            body["reply_parent_message_id"] = reply_parent_message_id

        headers = {
            "Client-Id": self.CLIENT_ID,
            "Authorization": f"Bearer {self.APP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as resp:
                if resp.status == 401:
                    self.APP_ACCESS_TOKEN = await self.get_app_access_token()
                    headers["Authorization"] = f"Bearer {self.APP_ACCESS_TOKEN}"

                    async with session.post(url, headers=headers, json=body) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()

                resp.raise_for_status()
                return await resp.json()

    # =====================================================
    # history helpers
    # =====================================================

    def add_to_history(self, username: str, text: str):
        self.CHAT_HISTORY.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "user": username,
            "text": text,
        })

    def print_history(self):
        print("\n===== HISTORY START =====")
        if not self.CHAT_HISTORY:
            print("История пуста.")
        else:
            for item in self.CHAT_HISTORY:
                print(f"[{item['time']}] {item['user']}: {item['text']}")
        print("===== HISTORY END =====\n")

    # =====================================================
    # message/trigger helpers
    # =====================================================

    def is_self_message(self, msg: ChatMessage) -> bool:
        return msg.user.name.lower() == self.BOT_LOGIN

    def is_ask_command_text(self, text: str) -> bool:
        return text.strip().lower().startswith("!ask")

    def is_reply_to_me(self, msg: ChatMessage) -> bool:
        if not msg.reply_parent_user_login:
            return False
        return msg.reply_parent_user_login.lower() == self.BOT_LOGIN

    def is_mention_to_me(self, text: str) -> bool:
        return bool(self.MENTION_PATTERN.search(text))

    def strip_mention(self, text: str) -> str:
        cleaned = self.MENTION_PATTERN.sub("", text, count=1).strip(" ,:;-")
        return cleaned.strip()

    def _has_badge(self, badges, badge_name: str) -> bool:
        for badge in badges or []:
            if getattr(badge, "set_id", "").lower() == badge_name.lower():
                return True
        return False

    # =====================================================
    # command builders
    # =====================================================

    def _build_chat_message(self, event) -> ChatMessage:
        reply = getattr(event, "reply", None)
        badges = getattr(event, "badges", None)

        return ChatMessage(
            bot=self,
            twitch=self.TWITCH_APP,
            broadcaster_id=self.BROADCASTER_ID,
            sender_id=self.BOT_USER_ID,
            room_name=event.broadcaster_user_login,
            user_id=event.chatter_user_id,
            user_name=event.chatter_user_login,
            text=event.message.text,
            message_id=event.message_id,
            reply_parent_msg_id=getattr(reply, "parent_message_id", None) if reply else None,
            reply_parent_msg_body=getattr(reply, "parent_message_body", None) if reply else None,
            reply_parent_user_login=getattr(reply, "parent_user_login", None) if reply else None,
            user_mod=self._has_badge(badges, "moderator"),
        )

    def _build_chat_command(self, msg: ChatMessage) -> ChatCommand:
        parts = msg.text.split(" ", 1)
        parameter = parts[1] if len(parts) > 1 else ""

        return ChatCommand(
            bot=self,
            twitch=self.TWITCH_APP,
            broadcaster_id=self.BROADCASTER_ID,
            sender_id=self.BOT_USER_ID,
            user_id=msg.user.id,
            user_name=msg.user.name,
            parameter=parameter,
            message_id=msg.id,
            reply_parent_msg_id=msg.reply_parent_msg_id,
            reply_parent_msg_body=msg.reply_parent_msg_body,
            reply_parent_user_login=msg.reply_parent_user_login,
            user_mod=msg.user.mod,
        )

    # =====================================================
    # command dispatch
    # =====================================================

    async def _dispatch_command(self, msg: ChatMessage) -> bool:
        text = msg.text.strip()
        if not text.startswith("!"):
            return False

        command_name = text[1:].split(" ", 1)[0].lower()
        cmd = self._build_chat_command(msg)

        if command_name == "ask":
            await self.cmd_ask(cmd)
            return True

        handler = self.commands.get(command_name)
        if handler:
            await handler(cmd)

        return True

    # =====================================================
    # ask logic
    # =====================================================

    async def handle_ask(self, chat_message: ChatMessage, source: str, ask_text: str):
        if self.is_streaming:
            answer = getAiResponse(chat_message.user.name, ask_text, self.CHAT_HISTORY)
            await chat_message.reply(answer)
        else:
            await chat_message.reply("Команда работает только на стриме!")

    async def cmd_ask(self, cmd: ChatCommand):
        if self.is_streaming:
            ask_text = cmd.parameter.strip()

            answer = getAiResponse(cmd.user.name, ask_text, self.CHAT_HISTORY)
            await cmd.reply(answer)
        else:
            await cmd.reply("Команда работает только на стриме!")

    # =====================================================
    # events
    # =====================================================

    async def on_message(self, event):
        msg = self._build_chat_message(event.event)

        print(f"[{msg.room.name}] {msg.user.name}: {msg.text}")
        self.add_to_history(msg.user.name, msg.text)

        if self.is_self_message(msg):
            return

        if await self._dispatch_command(msg):
            return

        text = msg.text.strip()

        if self.is_reply_to_me(msg):
            await self.handle_ask(msg, source="reply", ask_text=text)
            return

        if self.is_mention_to_me(text):
            ask_text = self.strip_mention(text)
            await self.handle_ask(msg, source="mention", ask_text=ask_text)
            return

    async def on_stream_online(self, data):
        self.is_streaming = True
        print("STREAM IS ONLINE!")

    async def on_stream_offline(self, data):
        self.is_streaming = False
        print("STREAM IS OFFLINE!")

    async def find_or_create_user(self, user_id):
        user = collection.find_one({"_id": user_id})
        if user is None:
            collection.insert_one({
                "_id": user_id,
                "balance": 0
            })

    async def on_channel_points_redeem(self, data):
        event = data.event
        print(event)

        if event.reward.title == "Пополнить 5.000 монет":
            await self.find_or_create_user(event.user_id)
            collection.update_one({"_id": event.user_id}, {"$inc": {"balance": 5000}})

    # =====================================================
    # runtime
    # =====================================================

    async def run(self):
        # -----------------------
        # Подключение бота
        # -----------------------
        twitch = await Twitch(self.CLIENT_ID, self.CLIENT_SECRET, authenticate_app=False)
        await twitch.set_user_authentication(self.TOKEN, USER_SCOPE, self.REFRESH_TOKEN)
        self.TWITCH_APP = twitch

        # Получаем ID канала и ID бота
        user = await first(twitch.get_users(logins=self.CHANNEL_NAME))
        self.BROADCASTER_ID = user.id

        # Указываем явный login бота, чтобы BOT_USER_ID не был None
        bot_user = await first(twitch.get_users(logins=[self.BOT_LOGIN]))
        self.BOT_USER_ID = bot_user.id

        # -----------------------
        # Загрузка когов
        # -----------------------
        for i in os.listdir("./cogs"):
            if i.endswith(".py") and not i.startswith("_"):
                self.load_extension(i[:-3])

        # -----------------------
        # EventSub для бота (чат, стрим онлайн/оффлайн)
        # -----------------------
        eventsub_bot = EventSubWebsocket(twitch)
        eventsub_bot.start()

        print("Бот подключен. Подписываюсь на EventSub (чат и стрим)...")
        await eventsub_bot.listen_channel_chat_message(self.BROADCASTER_ID, self.BOT_USER_ID, self.on_message)
        await eventsub_bot.listen_stream_online(self.BROADCASTER_ID, self.on_stream_online)
        await eventsub_bot.listen_stream_offline(self.BROADCASTER_ID, self.on_stream_offline)

        # -----------------------
        # EventSub для стримера (channel points)
        # -----------------------
        twitch_streamer = await Twitch(
            self.BROADCASTER_CLIENT_ID,
            self.BROADCASTER_CLIENT_SECRET,
            authenticate_app=False
        )
        await twitch_streamer.set_user_authentication(
            self.BROADCASTER_TOKEN,
            BROADCASTER_SCOPE,
            self.BROADCASTER_REFRESH_TOKEN
        )
        self.TWITCH_BROADCASTER_APP = twitch_streamer

        eventsub_streamer = EventSubWebsocket(twitch_streamer)
        eventsub_streamer.start()

        print("Подключен EventSub стримера для channel points...")
        await eventsub_streamer.listen_channel_points_custom_reward_redemption_add(
            self.BROADCASTER_ID,
            self.on_channel_points_redeem
        )

        print(f"Подключено к каналу: {self.CHANNEL_NAME}")

        # -----------------------
        # Ожидание событий
        # -----------------------
        try:
            await asyncio.Event().wait()
        finally:
            await eventsub_bot.stop()
            await eventsub_streamer.stop()
            await twitch.close()
            await twitch_streamer.close()


# =========================================================
# entrypoint
# =========================================================

if __name__ == "__main__":
    bot = Bot()
    asyncio.run(bot.run())