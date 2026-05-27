import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from faceit_client import FaceitError, PlayerNotFoundError, faceit
from formatters.messages import format_stats
from handlers.compare import _do_compare
from handlers.last import _fetch_and_show_last
from handlers.recent import _build_and_send
from handlers.stats import _load_card
from keyboards.inline import stats_keyboard

router = Router()
log = logging.getLogger(__name__)


class Form(StatesGroup):
    waiting_nick = State()
    waiting_compare_nick = State()


# Legacy reply-keyboard button labels — silently ignore them so they aren't
# treated as nicknames. Old clients may still see this keyboard until /start
# sends ReplyKeyboardRemove.
IGNORE_TEXTS = {
    "📊 Статистика",
    "📋 Последние матчи",
    "📈 Форма (20 матчей)",
    "⚔️ Сравнить игроков",
}

MAX_NICK_LEN = 64


def menu_kb(nick: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data=f"action:stats:{nick}"),
                InlineKeyboardButton(text="📋 Последние 10", callback_data=f"action:last:{nick}"),
            ],
            [
                InlineKeyboardButton(text="📈 Форма (20)", callback_data=f"action:recent:{nick}"),
                InlineKeyboardButton(text="⚔️ Сравнить", callback_data=f"action:compare:{nick}"),
            ],
        ]
    )


@router.message(StateFilter(Form.waiting_compare_nick), F.text & ~F.text.startswith("/"))
async def on_second_nick(message: Message, state: FSMContext):
    if message.text in IGNORE_TEXTS:
        return
    data = await state.get_data()
    nick1 = (data.get("compare_nick1") or "").strip()
    nick2 = message.text.strip()
    if not nick2:
        await message.answer("❓ Введи никнейм второго игрока.")
        return
    if len(nick2) > MAX_NICK_LEN:
        await message.answer("❓ Слишком длинный ник.")
        return
    await state.clear()
    if not nick1:
        await message.answer("⚠️ Контекст сравнения утерян. Введи ник заново.")
        return
    wait_msg = await message.answer(
        f"⏳ Сравниваю <b>{nick1}</b> и <b>{nick2}</b>...", parse_mode="HTML"
    )
    await _do_compare(nick1, nick2, wait_msg, edit=True)


@router.message(F.text & ~F.text.startswith("/"))
async def on_nick_input(message: Message, state: FSMContext):
    if message.text in IGNORE_TEXTS:
        return
    nick = message.text.strip()
    if not nick:
        await message.answer(
            "❓ Введи никнейм на Faceit.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if len(nick) > MAX_NICK_LEN:
        await message.answer("❓ Слишком длинный ник — не больше 64 символов.")
        return
    await state.update_data(last_nick=nick)
    await message.answer(
        f"🎯 Игрок: <b>{nick}</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=menu_kb(nick),
    )


@router.callback_query(F.data.startswith("action:"))
async def on_action(callback: CallbackQuery, state: FSMContext):
    try:
        _, action, nick = callback.data.split(":", 2)
    except ValueError:
        await callback.answer()
        return

    if action == "stats":
        await callback.answer("📊 Загружаю...")
        wait_msg = await callback.message.answer(
            f"⏳ Ищу <b>{nick}</b> на Faceit...", parse_mode="HTML"
        )
        try:
            player, stats, avg_kills = await _load_card(nick)
            await wait_msg.edit_text(
                format_stats(player, stats, avg_kills=avg_kills),
                parse_mode="HTML",
                reply_markup=stats_keyboard(nick),
            )
        except PlayerNotFoundError as e:
            await wait_msg.edit_text(f"❌ {e}")
        except FaceitError as e:
            await wait_msg.edit_text(f"⚠️ {e}")
        except Exception:
            log.exception("menu stats failed for %r", nick)
            await wait_msg.edit_text("🔥 Что-то пошло не так.")

    elif action == "last":
        await callback.answer("📋 Загружаю...")
        wait_msg = await callback.message.answer(
            f"⏳ Загружаю матчи <b>{nick}</b>...", parse_mode="HTML"
        )
        await _fetch_and_show_last(nick, wait_msg, edit=True)

    elif action == "recent":
        await callback.answer("📈 Считаю...")
        wait_msg = await callback.message.answer(
            f"⏳ Считаю форму <b>{nick}</b>...", parse_mode="HTML"
        )
        await _build_and_send(nick, wait_msg, edit=True)

    elif action == "compare":
        await callback.answer()
        await state.set_state(Form.waiting_compare_nick)
        await state.update_data(compare_nick1=nick)
        await callback.message.answer(
            f"⚔️ Сравнение с <b>{nick}</b>\n\nВведи ник второго игрока:",
            parse_mode="HTML",
        )

    else:
        await callback.answer()
