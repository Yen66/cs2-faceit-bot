import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from faceit_client import faceit, PlayerNotFoundError, FaceitError
from formatters.messages import format_recent
from handlers.last import _parse_match

router = Router()
log = logging.getLogger(__name__)


async def _fetch_match(match_id: str, player_id: str, started_at: int) -> dict | None:
    try:
        ms = await faceit.get_match_stats(match_id)
        return _parse_match(player_id, ms, started_at)
    except Exception:
        return None


async def _build_and_send(nickname: str, target: Message, edit: bool):
    """Shared body for /recent command and the keyboard callback."""
    async def _reply(text: str, **kw):
        if edit:
            await target.edit_text(text, **kw)
        else:
            await target.answer(text, **kw)

    try:
        player = await faceit.get_player(nickname)
        player_id = player["player_id"]
        current_elo = player.get("games", {}).get("cs2", {}).get("faceit_elo", 0)

        history = await faceit.get_history(player_id, limit=20)
        raw = history.get("items", [])

        tasks = [
            _fetch_match(m.get("match_id", ""), player_id, m.get("started_at", 0))
            for m in raw
            if m.get("match_id")
        ]
        results = await asyncio.gather(*tasks)
        matches = [r for r in results if r is not None]

        await _reply(format_recent(nickname, matches, current_elo), parse_mode="HTML")

    except PlayerNotFoundError as e:
        await _reply(f"❌ {e}\n\nПроверь правильность никнейма.")
    except FaceitError as e:
        await _reply(f"⚠️ {e}")
    except Exception:
        log.exception("recent failed for %r", nickname)
        await _reply("🔥 Не удалось посчитать форму.")


@router.message(Command("recent"))
async def cmd_recent(message: Message):
    """Handle /recent <nickname> — aggregate stats over the last 20 matches."""
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❓ Укажи никнейм:\n<code>/recent s1mple</code>",
            parse_mode="HTML",
        )
        return

    nickname = parts[1].strip()
    wait_msg = await message.answer(
        f"⏳ Считаю форму <b>{nickname}</b>...", parse_mode="HTML"
    )
    await _build_and_send(nickname, wait_msg, edit=True)


@router.callback_query(lambda c: c.data and c.data.startswith("recent_form:"))
async def cb_recent_form(callback: CallbackQuery):
    """Handle 'Form' button under /stats."""
    nickname = callback.data.split(":", 1)[1]
    await callback.answer("📈 Считаю форму...")
    wait_msg = await callback.message.answer(
        f"⏳ Считаю форму <b>{nickname}</b>...", parse_mode="HTML"
    )
    await _build_and_send(nickname, wait_msg, edit=True)
