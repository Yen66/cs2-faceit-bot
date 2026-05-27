from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Telegram allows up to 64 bytes (UTF-8) in callback_data.
_MAX_CB = 64


def _fits(data: str) -> bool:
    return len(data.encode("utf-8")) <= _MAX_CB


def stats_keyboard(nickname: str) -> InlineKeyboardMarkup:
    """Keyboard under /stats message. Omits buttons whose callback_data overflows 64 bytes."""
    rows = []

    refresh_cb = f"refresh_stats:{nickname}"
    last_cb = f"last_matches:{nickname}"
    recent_cb = f"recent_form:{nickname}"

    row1 = []
    if _fits(refresh_cb):
        row1.append(InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh_cb))
    if _fits(last_cb):
        row1.append(InlineKeyboardButton(text="📋 Матчи", callback_data=last_cb))
    if row1:
        rows.append(row1)

    if _fits(recent_cb):
        rows.append([InlineKeyboardButton(text="📈 Форма (20 матчей)", callback_data=recent_cb)])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def compare_keyboard(nick1: str, nick2: str) -> InlineKeyboardMarkup:
    """Keyboard under /compare message. Omits the swap button if it would overflow callback_data."""
    rows = []
    swap_cb = f"swap_compare:{nick2}:{nick1}"
    if _fits(swap_cb):
        rows.append([
            InlineKeyboardButton(text="🔄 Поменять местами", callback_data=swap_cb)
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
