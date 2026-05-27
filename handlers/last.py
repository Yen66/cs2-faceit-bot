import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from faceit_client import faceit, PlayerNotFoundError, FaceitError
from formatters.messages import format_last_matches

router = Router()
log = logging.getLogger(__name__)


def _parse_match(player_id: str, match_stats: dict, started_at: int) -> dict | None:
    """Extract player-specific stats from a single match payload."""
    rounds = match_stats.get("rounds") or []
    if not rounds:
        return None
    round0 = rounds[0]
    teams = round0.get("teams", [])
    round_stats = round0.get("round_stats", {})

    for team in teams:
        for p in team.get("players", []):
            if p.get("player_id") != player_id:
                continue
            # Found the player's team — read result strictly from here
            result = team.get("team_stats", {}).get("Team Win", team.get("team_stats", {}).get("Win", "0"))
            stats_obj = p.get("player_stats", {})
            kills_raw = stats_obj.get("Kills", "0")
            deaths_raw = stats_obj.get("Deaths", "1")
            try:
                assists = int(stats_obj.get("Assists", 0))
            except (ValueError, TypeError):
                assists = "—"
            try:
                kills_i = int(kills_raw)
                deaths_i = int(deaths_raw)
                kd = round(kills_i / max(deaths_i, 1), 2)
            except (ValueError, TypeError):
                kills_i = kills_raw
                deaths_i = deaths_raw
                kd = "?"
            try:
                adr = round(float(stats_obj.get("ADR", 0)), 1)
            except (ValueError, TypeError):
                adr = "?"
            return {
                "result": str(result),
                "map": round_stats.get("Map", "?"),
                "score": round_stats.get("Score", "?-?"),
                "kills": kills_i,
                "deaths": deaths_i,
                "assists": assists,
                "kd": kd,
                "adr": adr,
                "started_at": started_at,
            }
    return None


async def _fetch_match_safe(match_id: str, player_id: str, started_at: int) -> dict | None:
    try:
        match_stats = await faceit.get_match_stats(match_id)
        return _parse_match(player_id, match_stats, started_at)
    except Exception:
        return None


async def _fetch_and_show_last(nickname: str, target_message: Message, edit: bool = False):
    """Fetch last matches and send/edit message."""
    async def _reply(text: str):
        if edit:
            await target_message.edit_text(text, parse_mode="HTML")
        else:
            await target_message.answer(text, parse_mode="HTML")

    try:
        player = await faceit.get_player(nickname)
        player_id = player["player_id"]
        history = await faceit.get_history(player_id, limit=10)
        raw_matches = history.get("items", [])

        tasks = [
            _fetch_match_safe(m.get("match_id", ""), player_id, m.get("started_at", 0))
            for m in raw_matches
            if m.get("match_id")
        ]
        results = await asyncio.gather(*tasks)
        matches = [r for r in results if r is not None]

        kills_vals = [m["kills"] for m in matches if isinstance(m.get("kills"), int)]
        avg_kills = round(sum(kills_vals) / len(kills_vals), 1) if kills_vals else None

        await _reply(format_last_matches(nickname, matches, avg_kills=avg_kills))

    except PlayerNotFoundError as e:
        await _reply(f"❌ {e}")
    except FaceitError as e:
        await _reply(f"⚠️ {e}")
    except Exception:
        log.exception("last matches failed for %r", nickname)
        await _reply("🔥 Ошибка при загрузке матчей.")


@router.message(Command("last"))
async def cmd_last(message: Message):
    """Handle /last <nickname> command."""
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❓ Укажи никнейм:\n<code>/last s1mple</code>",
            parse_mode="HTML",
        )
        return

    nickname = parts[1].strip()
    wait_msg = await message.answer(f"⏳ Загружаю матчи <b>{nickname}</b>...", parse_mode="HTML")
    await _fetch_and_show_last(nickname, wait_msg, edit=True)


@router.callback_query(lambda c: c.data and c.data.startswith("last_matches:"))
async def cb_last_matches(callback: CallbackQuery):
    """Handle 'Last matches' button under /stats."""
    nickname = callback.data.split(":", 1)[1]
    await callback.answer("📋 Загружаю матчи...")
    wait_msg = await callback.message.answer(
        f"⏳ Загружаю матчи <b>{nickname}</b>...", parse_mode="HTML"
    )
    await _fetch_and_show_last(nickname, wait_msg, edit=True)
