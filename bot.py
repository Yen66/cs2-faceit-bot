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
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN
from faceit_client import faceit
from handlers import stats, last, compare, recent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(stats.router)
dp.include_router(last.router)
dp.include_router(recent.router)
dp.include_router(compare.router)


@dp.message(Command("start", "help"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>CS2 Faceit Stats Bot</b>\n\n"
        "📌 Команды:\n"
        "• <code>/stats s1mple</code> — карточка игрока\n"
        "• <code>/last s1mple</code> — последние 10 матчей\n"
        "• <code>/recent s1mple</code> — форма за последние 20 матчей\n"
        "• <code>/compare s1mple NiKo</code> — сравнение двух игроков\n\n"
        "Используй никнейм с <b>Faceit</b>, не Steam."
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
    await bot.delete_webhook()
    await faceit.close()
    await bot.session.close()
    log.info("Webhook removed, shutdown complete")


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
