import os
import re
import aiohttp
from dotenv import load_dotenv

load_dotenv()
timeout = aiohttp.ClientTimeout(total=30)

class WhoIsCog:
    def __init__(self, bot):
        self.bot = bot
        self.RIOT_API_KEY = os.getenv("RIOT_API_KEY")
        self.previous_act = None
        self.session: aiohttp.ClientSession | None = None
        self.ready = False # TODO: Set to True when Riot API access is enabled

    def get_commands(self):
        return {
            "whois": self.cmd_whois
        }

    def extract_number(self, name: str) -> int:
        cleaned = name.replace('\xa0', ' ')
        match = re.search(r'(\d+)$', cleaned)
        return int(match.group(1)) if match else -1

    def find_previous_act(self, items: list[dict]) -> dict | None:
        episodes = [item for item in items if item["type"] == "episode"]

        acts_by_episode = {}
        active_act = None

        for item in items:
            if item["type"] == "act":
                acts_by_episode.setdefault(item["parentId"], []).append(item)
                if item["isActive"]:
                    active_act = item

        if active_act is None:
            return None

        episodes_in_order = list(reversed(episodes))

        timeline = []

        for episode in episodes_in_order:
            episode_acts = acts_by_episode.get(episode["id"], [])
            episode_acts.sort(key=lambda x: self.extract_number(x["name"]))  # 1, 2, 3
            timeline.extend(episode_acts)

        for i, act in enumerate(timeline):
            if act["id"] == active_act["id"]:
                return timeline[i - 1] if i > 0 else None

        return None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=timeout, base_url="https://eu.api.riotgames.com")
        return self.session

    async def _riot_get_json(self, path: str, **params) -> dict:
        session = await self._ensure_session()
        params["api_key"] = self.RIOT_API_KEY

        async with session.get(path, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def close(self) -> None:
        if self.session is not None and not self.session.closed:
            await self.session.close()

    async def cmd_whois(self, cmd):
        if not self.ready:
            await cmd.reply("Команда в разработке.")
            return

        if self.previous_act is None:
            data = await self._riot_get_json(
                "/val/content/v1/contents",
                locale="ru-RU",
            )
            self.previous_act = self.find_previous_act(data["acts"])

            if self.previous_act is None:
                await cmd.reply("Не удалось определить прошлый акт.")
                return

        parts = cmd.parameter.strip().split()
        if not parts:
            await cmd.reply("Использование: !whois [номер в лидерборде]")
            return

        try:
            place = int(parts[0])
            if place < 1:
                raise ValueError
        except ValueError:
            await cmd.reply("Номер в лидерборде должен быть положительным целым числом.")
            return

        data = await self._riot_get_json(
            f"/val/ranked/v1/leaderboards/by-act/{self.previous_act['id']}",
            size=1,
            startIndex=place - 1,
        )

        players = data.get("players", [])
        if not players:
            await cmd.reply("Игрок с таким местом не найден.")
            return

        player = players[0]

        puuid = player.get("puuid")
        game_name = player.get("gameName")
        tag_line = player.get("tagLine")

        if not puuid or not game_name or not tag_line:
            await cmd.reply("Игрок скрыл свой профиль.")
            return

        data = await self._riot_get_json(
            f"/val/match/v1/matchlists/by-puuid/{puuid}"
        )
        history = data.get("history", [])
        # TODO: Verify the order of the match history returned by the Riot API
        history = history[:5]

        if not history:
            await cmd.reply(f"#{place} (прошлый акт): {game_name}#{tag_line} | Нет истории матчей")
            return

        kills_gen = 0
        deaths_gen = 0
        headshots_gen = 0
        shots = 0
        results_matches = []

        for match in history:
            # TODO: Parse gameStartTimeMillis into a datetime object if match timestamps are needed.
            # match_time = match["gameStartTimeMillis"]
            matchId = match["matchId"]

            cur_match = await self._riot_get_json(
                f"/val/match/v1/matches/{matchId}"
            )

            players = cur_match.get("players", [])
            teams = cur_match.get("teams", [])
            round_results = cur_match.get("roundResults", [])

            kills = 0
            deaths = 0
            headshots = 0
            bodyshots = 0
            legshots = 0
            team_id = None
            won = None

            for p in players:
                if p.get("puuid") == puuid:
                    team_id = p.get("teamId")
                    player_stats = p.get("stats", {})
                    kills = player_stats.get("kills", 0)
                    deaths = player_stats.get("deaths", 0)
                    break

            for round_item in round_results:
                player_stats_list = round_item.get("playerStats", [])
                for p in player_stats_list:
                    if p.get("puuid") == puuid:
                        damage = p.get("damage", {})
                        headshots += damage.get("headshots", 0)
                        bodyshots += damage.get("bodyshots", 0)
                        legshots += damage.get("legshots", 0)

            for team in teams:
                if team.get("teamId") == team_id:
                    won = team.get("won")
                    # TODO: Check how the Riot API represents a draw.
                    break

            kills_gen += kills
            deaths_gen += deaths
            headshots_gen += headshots
            shots += headshots + bodyshots + legshots
            results_matches.append("W" if won is True else "L" if won is False else "?")
            # TODO: Replace "?" once the exact draw/unknown result format is confirmed in the API response.

        kd = round(kills_gen / deaths_gen, 2) if deaths_gen else kills_gen
        hs = round((headshots_gen / shots) * 100, 2) if shots else 0.0

        await cmd.reply(
            f"#{place} (прошлый акт): {game_name}#{tag_line} | "
            f"Ласт 5: {' '.join(results_matches)} | "
            f"K/D: {kd} | HS: {hs}%"
        )

def setup(bot):
    return WhoIsCog(bot)