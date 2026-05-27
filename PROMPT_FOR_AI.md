Напиши полный рабочий проект Telegram-бота на Python для просмотра CS2 статистики через Faceit API. Никакого Steam API — только Faceit Open API v4.

## Стек
- Python 3.12
- aiogram 3.x (async)
- httpx (async HTTP)
- python-dotenv
- База данных не нужна — бот stateless

## Переменные окружения (.env)
```
BOT_TOKEN=...
FACEIT_API_KEY=...  # бесплатно на developers.faceit.com → App Studio
```

## Команды бота

### /stats <nickname>
Карточка игрока:
- ELO и уровень (1–10) с эмодзи (🔰⚔️🥉🥈🥇👑)
- K/D, хедшоты %, win rate, avg kills, всего матчей, флаг страны
- Под сообщением 3 inline-кнопки: [🔄 Обновить] [📋 Матчи] [📈 Форма (20 матчей)]

### /last <nickname>
Последние 10 матчей:
- Карта (без префикса de_), ✅/❌, счёт, K/D, время ("2ч назад", "вчера")
- Матч-статы грузить параллельно через asyncio.gather

### /recent <nickname>
Агрегат за последние 20 матчей:
- Текущий ELO, W/L, win rate, средний K/D
- Топ-5 карт с W/L по каждой
- Иконка формы: 🔥 если ≥70% побед, 🧊 если ≤30%, иначе 📊

### /compare <nick1> <nick2>
Side-by-side сравнение двух игроков:
- ELO, K/D, win rate, HS% с цветными кружками (🟢 победитель, ⚪ проигравший)
- Вердикт: кто лидирует по количеству метрик
- Кнопка [🔄 Поменять местами]

### /start, /help
Список команд с примерами.

## Faceit API endpoints
Base: `https://open.faceit.com/data/v4`
Auth: `Authorization: Bearer {FACEIT_API_KEY}`

- `GET /players?nickname={nick}&game=cs2` → player_id, elo, level, country
- `GET /players/{id}/stats/cs2` → lifetime: K/D, win rate, HS%, matches, avg kills
- `GET /players/{id}/history?game=cs2&limit=N` → список матчей
- `GET /matches/{match_id}/stats` → карта, счёт, статы каждого игрока

Игрок лежит в `rounds[0].teams[].players[]` — искать по `player_id`.
Win определяется через `team.team_stats["Team Win"]` (или `"Win"` как fallback).

## Кеширование (in-memory TTL, без Redis)
- `get_player` — 5 минут (ключ: nickname.lower())
- `get_stats` — 5 минут (ключ: player_id)
- `get_match_stats` — 1 час (завершённые матчи неизменяемы)
- `get_history` — не кешировать

Реализовать как класс `_TTLCache` с методами `get/set` и автоочисткой при переполнении (max_size=512).
FaceitClient — module-level singleton `faceit = FaceitClient()`.
В `main()` вызывать `await faceit.close()` при завершении.

## Обработка ошибок
- 404 → `PlayerNotFoundError`
- 429 → `FaceitError("Faceit API перегружен, попробуй через 30 секунд")`
- Нет CS2 статов → `FaceitError("У этого игрока нет статистики по CS2 на Faceit")`
- Одинаковые ники в /compare → "😄 Нельзя сравнивать игрока с самим собой!"
- В каждом хендлере `except Exception` с `log.exception(...)` → "🔥 ..." пользователю

## Inline-кнопки
Telegram ограничивает callback_data до 64 байт — проверять через `len(data.encode("utf-8")) <= 64` и не добавлять кнопку если не влезает.

## Структура файлов
```
cs2_faceit_bot/
├── bot.py
├── config.py
├── faceit_client.py
├── requirements.txt
├── .env.example
├── formatters/
│   ├── __init__.py
│   └── messages.py
├── handlers/
│   ├── __init__.py
│   ├── stats.py
│   ├── last.py
│   ├── recent.py
│   └── compare.py
└── keyboards/
    ├── __init__.py
    └── inline.py
```

## Требования к коду
1. Все файлы — полностью, без заглушек и TODO
2. `aiogram.client.default.DefaultBotProperties(parse_mode=ParseMode.HTML)` при создании Bot
3. HTML parse_mode везде (не MarkdownV2)
4. Один httpx.AsyncClient на весь жизненный цикл приложения (не создавать новый на каждый запрос)
5. В bot.py — graceful shutdown: `finally: await faceit.close(); await bot.session.close()`
6. Логирование через `logging.basicConfig` + `log = logging.getLogger(__name__)` в каждом модуле

Напиши все файлы по очереди, начиная с `faceit_client.py`.
