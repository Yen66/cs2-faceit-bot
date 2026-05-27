"""
CS2 Faceit Statistics Bot
=========================
Команды:
  /stats <nickname>         — статистика игрока (ELO, K/D, win rate, HS%)
  /last <nickname>          — последние 10 матчей
  /recent <nickname>        — форма за последние 20 матчей (агрегат)
  /compare <nick1> <nick2>  — сравнение двух игроков

Запуск локально (polling):
  python bot.py

Запуск на сервере (webhook):
  WEBHOOK_URL=https://your-app.onrender.com python bot.py
"""

import asyncio
import logging
import os

import aiohttp
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN
from faceit_client import faceit
from handlers import compare, last, menu, recent, stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class ClearStateOnCommand(BaseMiddleware):
    """Clears FSM state whenever a user sends a /command, so commands always
    work cleanly regardless of any in-progress flow (e.g. waiting_compare_nick)."""

    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            state: FSMContext | None = data.get("state")
            if state is not None:
                await state.clear()
        return await handler(event, data)


dp.message.outer_middleware(ClearStateOnCommand())

dp.include_router(stats.router)
dp.include_router(last.router)
dp.include_router(recent.router)
dp.include_router(compare.router)
dp.include_router(menu.router)


@dp.message(Command("start", "help"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>CS2 Faceit Stats Bot</b>\n\n"
        "Просто пришли ник на <b>Faceit</b> — я покажу кнопки выбора действия.\n\n"
        "Например: <code>s1mple</code>\n\n"
        "Также работают команды:\n"
        "• <code>/stats &lt;ник&gt;</code> — карточка игрока\n"
        "• <code>/last &lt;ник&gt;</code> — последние 10 матчей\n"
        "• <code>/recent &lt;ник&gt;</code> — форма за 20 матчей\n"
        "• <code>/compare &lt;ник1&gt; &lt;ник2&gt;</code> — сравнение",
        reply_markup=ReplyKeyboardRemove(),
    )


async def on_startup(app: web.Application):
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    log.info("Webhook set: %s%s", WEBHOOK_URL, WEBHOOK_PATH)


async def self_ping(app: web.Application):
    async def _ping():
        await asyncio.sleep(10)
        while True:
            try:
                async with aiohttp.ClientSession() as s:
                    await s.get(f"http://0.0.0.0:{PORT}/health")
            except Exception:
                pass
            await asyncio.sleep(240)
    asyncio.create_task(_ping())


async def on_shutdown(app: web.Application):
    # Intentionally NOT calling delete_webhook(): during Render rolling deploys
    # the old container shuts down AFTER the new one has already set the webhook,
    # so deleting it here leaves Telegram pointing at nothing. on_startup is
    # idempotent and re-points the webhook on each container start.
    await faceit.close()
    await bot.session.close()
    log.info("Shutdown complete (webhook preserved)")


def run_webhook():
    app = web.Application()

    # Health check — Render pings this to keep the service alive
    async def health(request):
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_startup.append(self_ping)
    app.on_shutdown.append(on_shutdown)

    log.info("Starting webhook server on port %d", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)


async def run_polling():
    log.info("Starting in polling mode")
    try:
        await dp.start_polling(bot)
    finally:
        await faceit.close()
        await bot.session.close()


if __name__ == "__main__":
    if WEBHOOK_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
