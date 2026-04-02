import os
import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("BROADCASTER_CLIENT_ID")
CLIENT_SECRET = os.getenv("BROADCASTER_CLIENT_SECRET")

USER_SCOPE = [
    AuthScope.CHANNEL_READ_REDEMPTIONS,
    AuthScope.CHANNEL_MANAGE_REDEMPTIONS
]

async def main():
    twitch = await Twitch(CLIENT_ID, CLIENT_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)
    token, refresh_token = await auth.authenticate()

    print("ACCESS TOKEN:")
    print(token)
    print("\nREFRESH TOKEN:")
    print(refresh_token)

    await twitch.close()

asyncio.run(main())