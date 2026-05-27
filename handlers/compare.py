import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from faceit_client import faceit, PlayerNotFoundError, FaceitError
from formatters.messages import format_compare_recent
from keyboards.inline import compare_keyboard

router = Router()
log = logging.getLogger(__name__)

RECENT_LIMIT = 20


async def _aggregate_recent(player_id: str, limit: int = RECENT_LIMIT) -> dict:
    """Fetch the player's last `limit` matches and compute wins/losses/avg K/D/avg HS%."""
    history = await faceit.get_history(player_id, limit=limit)
    raw = history.get("items", [])

    async def _safe_stats(match_id: str):
        try:
            return await faceit.get_match_stats(match_id)
        except Exception:
            return None

    tasks = [_safe_stats(m.get("match_id", "")) for m in raw if m.get("match_id")]
    results = await asyncio.gather(*tasks)

    wins = losses = 0
    kds: list[float] = []
    hss: list[float] = []

    for match_stats in results:
        if not match_stats:
            continue
        rounds = match_stats.get("rounds") or []
        if not rounds:
            continue
        for team in rounds[0].get("teams", []):
            found = False
            for p in team.get("players", []):
                if p.get("player_id") != player_id:
                    continue
                found = True
                team_stats = team.get("team_stats", {})
                won = str(team_stats.get("Team Win", team_stats.get("Win", "0"))) == "1"
                if won:
                    wins += 1
                else:
                    losses += 1
                ps = p.get("player_stats", {})
                try:
                    k = int(ps.get("Kills", 0))
                    d = max(int(ps.get("Deaths", 1)), 1)
                    kds.append(k / d)
                except (ValueError, TypeError):
                    pass
                try:
                    hss.append(float(ps.get("Headshots %", 0)))
                except (ValueError, TypeError):
                    pass
                break
            if found:
                break

    n = wins + losses
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / n * 100, 1) if n else 0.0,
        "avg_kd": round(sum(kds) / len(kds), 2) if kds else 0.0,
        "avg_hs": round(sum(hss) / len(hss), 1) if hss else 0.0,
    }


async def _do_compare(nick1: str, nick2: str, target: Message, edit: bool = False):
    """Fetch both players and send comparison based on last 20 matches."""
    async def _reply(text: str, **kw):
        if edit:
            await target.edit_text(text, **kw)
        else:
            await target.answer(text, **kw)

    if nick1.lower() == nick2.lower():
        await _reply("😄 Нельзя сравнивать игрока с самим собой!")
        return

    try:
        p1, p2 = await asyncio.gather(
            faceit.get_player(nick1),
            faceit.get_player(nick2),
        )
        a1, a2 = await asyncio.gather(
            _aggregate_recent(p1["player_id"]),
            _aggregate_recent(p2["player_id"]),
        )
        if a1["n"] == 0 or a2["n"] == 0:
            empty = nick1 if a1["n"] == 0 else nick2
            await _reply(f"😔 Нет недавних матчей у <b>{empty}</b> для сравнения.", parse_mode="HTML")
            return
        text = format_compare_recent(p1, a1, p2, a2)
        kb = compare_keyboard(nick1, nick2)
        await _reply(text, parse_mode="HTML", reply_markup=kb)

    except PlayerNotFoundError as e:
        await _reply(f"❌ {e}")
    except FaceitError as e:
        await _reply(f"⚠️ {e}")
    except Exception:
        log.exception("compare failed for %r vs %r", nick1, nick2)
        await _reply("🔥 Ошибка при сравнении игроков.")


@router.message(Command("compare"))
async def cmd_compare(message: Message):
    """Handle /compare <nick1> <nick2> command."""
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer(
            "❓ Укажи два никнейма:\n<code>/compare s1mple NiKo</code>",
            parse_mode="HTML",
        )
        return

    nick1, nick2 = parts[1], parts[2]
    wait_msg = await message.answer(
        f"⏳ Сравниваю <b>{nick1}</b> и <b>{nick2}</b>...", parse_mode="HTML"
    )
    await _do_compare(nick1, nick2, wait_msg, edit=True)


@router.callback_query(lambda c: c.data and c.data.startswith("swap_compare:"))
async def cb_swap_compare(callback: CallbackQuery):
    """Handle 'Swap players' button."""
    _, nick1, nick2 = callback.data.split(":", 2)
    await callback.answer("🔄 Меняю местами...")
    await _do_compare(nick1, nick2, callback.message, edit=True)
