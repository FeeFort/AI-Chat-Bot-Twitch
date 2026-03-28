import os
import asyncio
import re
import random
from collections import deque
from datetime import datetime

import aiohttp
from pathlib import Path
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first
from get_response import getAiResponse

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
CHANNEL_NAME = os.getenv("TWITCH_CHANNEL_NAME")
TOKEN = os.getenv("TWITCH_USER_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("TWITCH_USER_REFRESH_TOKEN")

USER_SCOPE = [
    AuthScope.USER_BOT,
    AuthScope.USER_READ_CHAT,
    AuthScope.USER_WRITE_CHAT,
]

# Храним последние N сообщений в памяти
MAX_HISTORY = 100
CHAT_HISTORY = deque(maxlen=MAX_HISTORY)

# Логин, на который реагируем как на "упоминание бота"
BOT_LOGIN = "pa1kamod"

# Ищем "pa1ka" или "@pa1ka" как отдельное слово
MENTION_PATTERN = re.compile(rf"(?<!\w)@?{re.escape(BOT_LOGIN)}(?!\w)", re.IGNORECASE)
MENTION_RE = re.compile(r"^@?([a-zA-Z0-9_]{4,25})(?:\s+(.*))?$")

is_streaming = False

TWITCH_APP = None
BROADCASTER_ID = None
BOT_USER_ID = None
APP_ACCESS_TOKEN = None


class _CompatChatRoom:
    def __init__(self, name: str):
        self.name = name


class _CompatChatUser:
    def __init__(self, user_id: str, name: str, mod: bool = False):
        self.id = user_id
        self.name = name
        self.mod = mod


async def get_app_access_token() -> str:
    url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            resp.raise_for_status()
            payload = await resp.json()
            return payload["access_token"]


async def send_chat_message_api(
    broadcaster_id: str,
    sender_id: str,
    message: str,
    reply_parent_message_id: str | None = None,
):
    global APP_ACCESS_TOKEN

    if APP_ACCESS_TOKEN is None:
        APP_ACCESS_TOKEN = await get_app_access_token()

    url = "https://api.twitch.tv/helix/chat/messages"

    body = {
        "broadcaster_id": broadcaster_id,
        "sender_id": sender_id,
        "message": message,
    }

    if reply_parent_message_id:
        body["reply_parent_message_id"] = reply_parent_message_id

    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {APP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=body) as resp:
            if resp.status == 401:
                APP_ACCESS_TOKEN = await get_app_access_token()
                headers["Authorization"] = f"Bearer {APP_ACCESS_TOKEN}"

                async with session.post(url, headers=headers, json=body) as retry_resp:
                    retry_resp.raise_for_status()
                    return await retry_resp.json()

            resp.raise_for_status()
            return await resp.json()


class ChatMessage:
    def __init__(
        self,
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
        await send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
            reply_parent_message_id=self.id,
        )


class ChatCommand:
    def __init__(
        self,
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
        await send_chat_message_api(
            self._broadcaster_id,
            self._sender_id,
            text,
            reply_parent_message_id=self.id,
        )


def add_to_history(username: str, text: str):
    CHAT_HISTORY.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": username,
        "text": text,
    })


def print_history():
    print("\n===== HISTORY START =====")
    if not CHAT_HISTORY:
        print("История пуста.")
    else:
        for item in CHAT_HISTORY:
            print(f"[{item['time']}] {item['user']}: {item['text']}")
    print("===== HISTORY END =====\n")


def is_self_message(msg: ChatMessage) -> bool:
    return msg.user.name.lower() == BOT_LOGIN


def is_ask_command_text(text: str) -> bool:
    return text.strip().lower().startswith("!ask")


def is_reply_to_me(msg: ChatMessage) -> bool:
    if not msg.reply_parent_user_login:
        return False
    return msg.reply_parent_user_login.lower() == BOT_LOGIN


def is_mention_to_me(text: str) -> bool:
    return bool(MENTION_PATTERN.search(text))


def strip_mention(text: str) -> str:
    cleaned = MENTION_PATTERN.sub("", text, count=1).strip(" ,:;-")
    return cleaned.strip()


def make_ask_payload(source: str, username: str, text: str, reply_to: str | None = None) -> dict:
    return {
        "source": source,          # command | reply | mention
        "username": username,
        "text": text,
        "reply_to": reply_to,
        "history": list(CHAT_HISTORY),
    }


def generate_placeholder_answer(payload: dict) -> str:
    """
    ВРЕМЕННАЯ ЗАГЛУШКА.
    Позже здесь можно будет вызвать LLM API и вернуть сгенерированный ответ.
    """
    source = payload["source"]
    username = payload["username"]
    text = payload["text"]

    if not text:
        return f"{username}, вопрос пустой"

    return f"[stub:{source}] {username}: {text}"


def _has_badge(badges, badge_name: str) -> bool:
    for badge in badges or []:
        if getattr(badge, "set_id", "").lower() == badge_name.lower():
            return True
    return False


def _build_chat_message(event) -> ChatMessage:
    reply = getattr(event, "reply", None)
    badges = getattr(event, "badges", None)

    return ChatMessage(
        twitch=TWITCH_APP,
        broadcaster_id=BROADCASTER_ID,
        sender_id=BOT_USER_ID,
        room_name=event.broadcaster_user_login,
        user_id=event.chatter_user_id,
        user_name=event.chatter_user_login,
        text=event.message.text,
        message_id=event.message_id,
        reply_parent_msg_id=getattr(reply, "parent_message_id", None) if reply else None,
        reply_parent_msg_body=getattr(reply, "parent_message_body", None) if reply else None,
        reply_parent_user_login=getattr(reply, "parent_user_login", None) if reply else None,
        user_mod=_has_badge(badges, "moderator"),
    )


def _build_chat_command(msg: ChatMessage) -> ChatCommand:
    parts = msg.text.split(" ", 1)
    parameter = parts[1] if len(parts) > 1 else ""

    return ChatCommand(
        twitch=TWITCH_APP,
        broadcaster_id=BROADCASTER_ID,
        sender_id=BOT_USER_ID,
        user_id=msg.user.id,
        user_name=msg.user.name,
        parameter=parameter,
        message_id=msg.id,
        reply_parent_msg_id=msg.reply_parent_msg_id,
        reply_parent_msg_body=msg.reply_parent_msg_body,
        reply_parent_user_login=msg.reply_parent_user_login,
        user_mod=msg.user.mod,
    )


async def _dispatch_command(msg: ChatMessage) -> bool:
    text = msg.text.strip()
    if not text.startswith("!"):
        return False

    command_name = text[1:].split(" ", 1)[0].lower()
    cmd = _build_chat_command(msg)

    if command_name == "ping":
        await cmd_ping(cmd)
        return True

    if command_name == "hello":
        await cmd_hello(cmd)
        return True

    if command_name == "history":
        await cmd_history(cmd)
        return True

    if command_name == "ask":
        await cmd_ask(cmd)
        return True

    if command_name == "stream":
        await cmd_stream(cmd)
        return True

    #chat.register_command("hack", cmd_hack)
    return True


async def handle_ask(chat_message: ChatMessage, source: str, ask_text: str):
    if is_streaming:
        payload = make_ask_payload(
            source=source,
            username=chat_message.user.name,
            text=ask_text,
            reply_to=chat_message.reply_parent_msg_body if chat_message.reply_parent_msg_body else None,
        )

        answer = getAiResponse(chat_message.user.name, ask_text, CHAT_HISTORY)
        await chat_message.reply(answer)
    else:
        await chat_message.reply("Команда работает только на стриме!")


async def on_message(event):
    msg = _build_chat_message(event.event)

    print(f"[{msg.room.name}] {msg.user.name}: {msg.text}")
    add_to_history(msg.user.name, msg.text)

    if is_self_message(msg):
        return

    if await _dispatch_command(msg):
        return

    text = msg.text.strip()

    if is_reply_to_me(msg):
        await handle_ask(msg, source="reply", ask_text=text)
        return

    if is_mention_to_me(text):
        ask_text = strip_mention(text)
        await handle_ask(msg, source="mention", ask_text=ask_text)
        return


async def on_stream_online(data):
    global is_streaming
    is_streaming = True


async def on_stream_offline(data):
    global is_streaming
    is_streaming = False


async def cmd_ping(cmd: ChatCommand):
    await cmd.reply("pong")


async def cmd_hello(cmd: ChatCommand):
    await cmd.reply(f"Привет, {cmd.user.name}")


async def cmd_history(cmd: ChatCommand):
    print_history()
    await cmd.reply("история выведена в консоль")


async def cmd_stream(cmd: ChatCommand):
    global is_streaming

    is_broadcaster = cmd.user.name.lower() == CHANNEL_NAME.lower()
    is_moderator = cmd.user.mod

    if not (is_broadcaster or is_moderator):
        await cmd.reply("Не твоя кнопка.")
        return

    raw = (cmd.parameter or "").strip().lower()

    if not raw:
        status = "ON" if is_streaming else "OFF"
        await cmd.reply(f"stream = {status}")
        return

    if raw == "on":
        is_streaming = True
        print("STREAM FLAG MANUALLY SET TO: ON")
        await cmd.reply("stream mode: ON")
        return

    if raw == "off":
        is_streaming = False
        print("STREAM FLAG MANUALLY SET TO: OFF")
        await cmd.reply("stream mode: OFF")
        return

    await cmd.reply("Используй: !stream on или !stream off")


async def cmd_hack(cmd: ChatCommand):
    raw = (cmd.parameter or "").strip()

    if not raw:
        await cmd.reply("Укажи пользователя: !hack @nickname")
        return

    match = MENTION_RE.match(raw)
    if not match:
        await cmd.reply("Формат такой: !hack @nickname")
        return

    target_user = match.group(1)

    await cmd.reply(f"{target_user}, you've been hacked: ip: {'.'.join(str(random.randint(1,255)) for _ in range(4))}, N: {random.uniform(0,90):.4f}, W: {random.uniform(0,180):.4f}, DMZ: 10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}, DNS: 8.8.8.8, ALT DNS: 1.1.1.1, WAN TYPE: Private Nat, Gateway: 192.168.1.254, Subnet Mask: 255.255.255.0, udp open ports 80 25565, tcp open ports 443 25565, Router Vendor: ERICSON, Device Vendor: WIN32X, MAC: 5A:78:3E:7E:00..., ISP: Ucom Universal, UPNP: Enabled")


async def cmd_ask(cmd: ChatCommand):
    if is_streaming:
        ask_text = cmd.parameter.strip()

        payload = make_ask_payload(
            source="command",
            username=cmd.user.name,
            text=ask_text,
            reply_to=cmd.reply_parent_msg_body if cmd.reply_parent_msg_body else None,
        )

        answer = getAiResponse(cmd.user.name, ask_text, CHAT_HISTORY)
        await cmd.reply(answer)
    else:
        await cmd.reply("Команда работает только на стриме!")


async def run():
    global TWITCH_APP, BROADCASTER_ID, BOT_USER_ID

    twitch = await Twitch(CLIENT_ID, CLIENT_SECRET, authenticate_app=False)
    await twitch.set_user_authentication(TOKEN, USER_SCOPE, REFRESH_TOKEN)

    TWITCH_APP = twitch

    user = await first(twitch.get_users(logins=CHANNEL_NAME))
    BROADCASTER_ID = user.id

    bot_user = await first(twitch.get_users())
    BOT_USER_ID = bot_user.id

    eventsub = EventSubWebsocket(twitch)
    eventsub.start()

    print("Бот подключен. Подписываюсь на EventSub...")
    await eventsub.listen_channel_chat_message(BROADCASTER_ID, BOT_USER_ID, on_message)
    await eventsub.listen_stream_online(BROADCASTER_ID, on_stream_online)
    await eventsub.listen_stream_offline(BROADCASTER_ID, on_stream_offline)
    print(f"Подключено к каналу: {CHANNEL_NAME}")

    try:
        await asyncio.Event().wait()
    finally:
        await eventsub.stop()
        await twitch.close()


if __name__ == "__main__":
    asyncio.run(run())