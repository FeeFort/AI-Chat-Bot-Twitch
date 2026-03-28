import os
import asyncio
import re
import random
from collections import deque
from datetime import datetime

from pathlib import Path
from dotenv import load_dotenv
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatCommand
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first
from get_response import getAiResponse

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
CHANNEL_NAME = os.getenv("TWITCH_CHANNEL_NAME")
TOKEN = os.getenv("TWITCH_USER_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("TWITCH_USER_REFRESH_TOKEN")

USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT]

# Храним последние N сообщений в памяти
MAX_HISTORY = 100
CHAT_HISTORY = deque(maxlen=MAX_HISTORY)

# Логин, на который реагируем как на "упоминание бота"
BOT_LOGIN = "pa1kamod"

# Ищем "pa1ka" или "@pa1ka" как отдельное слово
MENTION_PATTERN = re.compile(rf"(?<!\w)@?{re.escape(BOT_LOGIN)}(?!\w)", re.IGNORECASE)
MENTION_RE = re.compile(r"^@?([a-zA-Z0-9_]{4,25})(?:\s+(.*))?$")

is_streaming = False


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


async def handle_ask(chat_message: ChatMessage, source: str, ask_text: str):
    if is_streaming:
        payload = make_ask_payload(
            source=source,
            username=chat_message.user.name,
            text=ask_text,
            reply_to=chat_message.reply_parent_msg_body if chat_message.reply_parent_msg_body else None,
        )

        print("\n===== ASK PAYLOAD START =====")
        print(payload)
        print("===== ASK PAYLOAD END =====\n")

        answer = getAiResponse(chat_message.user.name, ask_text, CHAT_HISTORY)
        await chat_message.reply(answer)
    else:
        await chat_message.reply("Команда работает только на стриме!")



async def on_ready(ready_event: EventData):
    print("Бот подключен. Захожу в канал...")
    await ready_event.chat.join_room(CHANNEL_NAME)
    print(f"Подключено к каналу: {CHANNEL_NAME}")


async def on_message(msg: ChatMessage):
    print(f"[{msg.room.name}] {msg.user.name}: {msg.text}")
    add_to_history(msg.user.name, msg.text)

    # Не реагируем на свои собственные сообщения, иначе возможна петля
    if is_self_message(msg):
        return

    text = msg.text.strip()

    # Команды обрабатываются отдельно через register_command()
    # Здесь пропускаем любые сообщения, начинающиеся с !
    if text.startswith("!"):
        return

    # 1) Триггер через reply
    if is_reply_to_me(msg):
        await handle_ask(msg, source="reply", ask_text=text)
        return

    # 2) Триггер через упоминание логина
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

        print("\n===== ASK PAYLOAD START =====")
        print(payload)
        print("===== ASK PAYLOAD END =====\n")

        answer = getAiResponse(cmd.user.name, ask_text, CHAT_HISTORY)
        await cmd.reply(answer)
    else:
        await cmd.reply("Команда работает только на стриме!")


async def run():
    twitch = await Twitch(CLIENT_ID, CLIENT_SECRET)
    await twitch.set_user_authentication(TOKEN, USER_SCOPE, REFRESH_TOKEN)

    user = await first(twitch.get_users(logins=CHANNEL_NAME))
    BROADCASTER_ID = user.id

    chat = await Chat(twitch)
    eventsub = EventSubWebsocket(twitch)
    eventsub.start()

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    await eventsub.listen_stream_online(BROADCASTER_ID, on_stream_online)
    await eventsub.listen_stream_offline(BROADCASTER_ID, on_stream_offline)

    chat.register_command("ping", cmd_ping)
    chat.register_command("hello", cmd_hello)
    chat.register_command("history", cmd_history)
    chat.register_command("ask", cmd_ask)
    #chat.register_command("hack", cmd_hack)

    chat.start()

    try:
        await asyncio.Event().wait()
    finally:
        chat.stop()
        await twitch.close()


if __name__ == "__main__":
    asyncio.run(run())