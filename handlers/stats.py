import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from faceit_client import faceit, PlayerNotFoundError, FaceitError
from formatters.messages import format_stats
from handlers.compare import _aggregate_recent
from keyboards.inline import stats_keyboard

router = Router()
log = logging.getLogger(__name__)


async def _load_card(nickname: str):
    """Fetch player + lifetime stats + last-20 aggregate in parallel."""
    player = await faceit.get_player(nickname)
    stats, agg = await asyncio.gather(
        faceit.get_stats(player["player_id"]),
        _aggregate_recent(player["player_id"]),
    )
    return player, stats, agg.get("avg_kills", 0.0)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats <nickname> command."""
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❓ Укажи никнейм на Faceit:\n"
            "<code>/stats s1mple</code>",
            parse_mode="HTML",
        )
        return

    nickname = parts[1].strip()
    wait_msg = await message.answer(f"⏳ Ищу <b>{nickname}</b> на Faceit...", parse_mode="HTML")

    try:
        player, stats, avg_kills = await _load_card(nickname)
        text = format_stats(player, stats, avg_kills=avg_kills)
        kb = stats_keyboard(nickname)
        await wait_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)

    except PlayerNotFoundError as e:
        await wait_msg.edit_text(f"❌ {e}\n\nПроверь правильность написания никнейма.")
    except FaceitError as e:
        await wait_msg.edit_text(f"⚠️ {e}")
    except Exception:
        log.exception("cmd_stats failed for %r", nickname)
        await wait_msg.edit_text("🔥 Что-то пошло не так. Попробуй снова.")


@router.callback_query(lambda c: c.data and c.data.startswith("refresh_stats:"))
async def cb_refresh_stats(callback: CallbackQuery):
    """Handle 'Refresh' button under stats."""
    nickname = callback.data.split(":", 1)[1]
    await callback.answer("🔄 Обновляю...")

    try:
        player, stats, avg_kills = await _load_card(nickname)
        text = format_stats(player, stats, avg_kills=avg_kills)
        kb = stats_keyboard(nickname)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except (PlayerNotFoundError, FaceitError) as e:
        await callback.message.answer(f"❌ {e}")
    except Exception:
        log.exception("cb_refresh_stats failed for %r", nickname)
        await callback.message.answer("🔥 Не удалось обновить.")
