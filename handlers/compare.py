import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from faceit_client import faceit, PlayerNotFoundError, FaceitError
from formatters.messages import format_compare
from keyboards.inline import compare_keyboard

router = Router()
log = logging.getLogger(__name__)


async def _do_compare(nick1: str, nick2: str, target: Message, edit: bool = False):
    """Fetch both players and send comparison."""
    async def _reply(text: str, **kw):
        if edit:
            await target.edit_text(text, **kw)
        else:
            await target.answer(text, **kw)

    if nick1.lower() == nick2.lower():
        await _reply("😄 Нельзя сравнивать игрока с самим собой!")
        return

    try:
        p1 = await faceit.get_player(nick1)
        p2 = await faceit.get_player(nick2)
        s1 = await faceit.get_stats(p1["player_id"])
        s2 = await faceit.get_stats(p2["player_id"])
        text = format_compare(p1, s1, p2, s2)
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
