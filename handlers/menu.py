import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from faceit_client import FaceitError, PlayerNotFoundError
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


# Text of the new persistent reply-keyboard action buttons → internal action name.
# Must NOT overlap with command syntax; texts here mirror the inline menu labels.
ACTION_BUTTONS = {
    "📊 Статистика": "stats",
    "📋 Последние 10": "last",
    "📈 Форма (20)": "recent",
    "⚔️ Сравнить": "compare",
}

# Older reply-keyboard labels from prior versions — no longer in use but old
# clients may still see them. Recognise and prompt the user instead of treating
# them as nicknames. "📊 Статистика" was reused for the new keyboard and is
# intentionally NOT listed here.
LEGACY_BUTTONS = {
    "📋 Последние матчи",
    "📈 Форма (20 матчей)",
    "⚔️ Сравнить игроков",
}

HISTORY_PREFIX = "👤 "
MAX_NICK_LEN = 64
MAX_HISTORY = 5


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


def make_nick_keyboard(nick: str, history: list[str]) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📋 Последние 10")],
        [KeyboardButton(text="📈 Форма (20)"), KeyboardButton(text="⚔️ Сравнить")],
    ]
    if history:
        rows.append([KeyboardButton(text=f"{HISTORY_PREFIX}{n}") for n in history[:MAX_HISTORY]])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Введи никнейм...",
    )


def _push_history(history: list[str], nick: str) -> list[str]:
    """Move nick to head; dedupe; cap at MAX_HISTORY."""
    history = [n for n in history if n != nick]
    history.insert(0, nick)
    return history[:MAX_HISTORY]


async def _run_action(action: str, nick: str, target: Message, state: FSMContext):
    """Execute a stats/last/recent/compare action. Used by both inline-callback
    and reply-keyboard paths."""
    if action == "stats":
        wait_msg = await target.answer(
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
            log.exception("action stats failed for %r", nick)
            await wait_msg.edit_text("🔥 Что-то пошло не так.")

    elif action == "last":
        wait_msg = await target.answer(
            f"⏳ Загружаю матчи <b>{nick}</b>...", parse_mode="HTML"
        )
        await _fetch_and_show_last(nick, wait_msg, edit=True)

    elif action == "recent":
        wait_msg = await target.answer(
            f"⏳ Считаю форму <b>{nick}</b>...", parse_mode="HTML"
        )
        await _build_and_send(nick, wait_msg, edit=True)

    elif action == "compare":
        await state.set_state(Form.waiting_compare_nick)
        await state.update_data(compare_nick1=nick)
        await target.answer(
            f"⚔️ Сравнение с <b>{nick}</b>\n\nВведи ник второго игрока:",
            parse_mode="HTML",
        )


@router.message(
    StateFilter(Form.waiting_compare_nick),
    F.text
    & ~F.text.startswith("/")
    & ~F.text.in_(set(ACTION_BUTTONS.keys()))
    & ~F.text.startswith(HISTORY_PREFIX),
)
async def on_second_nick(message: Message, state: FSMContext):
    if message.text in LEGACY_BUTTONS:
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


@router.message(F.text.in_(set(ACTION_BUTTONS.keys())))
async def on_reply_action(message: Message, state: FSMContext):
    """User pressed an action button on the persistent reply keyboard."""
    data = await state.get_data()
    nick = (data.get("last_nick") or "").strip()
    if not nick:
        await message.answer("Сначала введи никнейм 👇")
        return
    action = ACTION_BUTTONS[message.text]
    await _run_action(action, nick, message, state)


@router.message(F.text.startswith(HISTORY_PREFIX))
async def on_history_nick(message: Message, state: FSMContext):
    """User pressed one of the 👤 history buttons — switch active nick and show inline menu."""
    nick = message.text[len(HISTORY_PREFIX):].strip()
    if not nick or len(nick) > MAX_NICK_LEN:
        return
    data = await state.get_data()
    history = _push_history(list(data.get("nick_history", [])), nick)
    await state.update_data(last_nick=nick, nick_history=history)
    await message.answer(
        f"🎯 Игрок: <b>{nick}</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=menu_kb(nick),
    )


@router.message(F.text & ~F.text.startswith("/"))
async def on_nick_input(message: Message, state: FSMContext):
    if message.text in LEGACY_BUTTONS:
        await message.answer(
            "👆 Эти кнопки устарели — просто введи никнейм на Faceit и я покажу меню.",
            reply_markup=ReplyKeyboardRemove(),
        )
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

    data = await state.get_data()
    history = _push_history(list(data.get("nick_history", [])), nick)
    await state.update_data(last_nick=nick, nick_history=history)

    await message.answer(
        f"🎯 Игрок: <b>{nick}</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=make_nick_keyboard(nick, history),
    )


@router.callback_query(F.data.startswith("action:"))
async def on_action(callback: CallbackQuery, state: FSMContext):
    try:
        _, action, nick = callback.data.split(":", 2)
    except ValueError:
        await callback.answer()
        return

    answer_hint = {
        "stats": "📊 Загружаю...",
        "last": "📋 Загружаю...",
        "recent": "📈 Считаю...",
        "compare": "",
    }.get(action, "")
    await callback.answer(answer_hint)
    await _run_action(action, nick, callback.message, state)
