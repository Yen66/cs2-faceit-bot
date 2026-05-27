# cs2-faceit-bot — operating rules

## ЗАПРЕЩЕНО

- **Никогда не запускать `python bot.py`** — это убивает webhook на Render (общий BOT_TOKEN). Polling против активного webhook несовместим.
- Для проверки синтаксиса использовать только: `python -m py_compile bot.py handlers/*.py formatters/*.py`
- Не вызывать `bot.delete_webhook()` нигде в коде — webhook должен переживать перезапуски контейнера.

## Как деплоить

1. Внести изменения.
2. Запустить `./deploy.sh "commit message"` — он сделает syntax check, commit, push и через ~2.5 мин переустановит webhook на всякий случай.
3. Render задеплоит автоматически (auto-deploy включён на ветке `main`).

Альтернатива (если deploy.sh недоступен):
```
python -m py_compile bot.py handlers/*.py formatters/*.py
git add -A && git commit -m "..." && git push
```
После пуша Render сам поднимает контейнер и `on_startup` восстанавливает webhook через `set_webhook()`.

## Если бот не отвечает

1. Проверить webhook: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`
2. Если `url=""` — восстановить: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://cs2-faceit-bot.onrender.com/webhook"`
3. Проверить health: `curl https://cs2-faceit-bot.onrender.com/health` → должно быть `OK`.

## Полезные ID

- Render service: `srv-d8bhktnavr4c739k5f7g` (URL `https://cs2-faceit-bot.onrender.com`)
- UptimeRobot monitor: `803168608` (пинг каждые 5 мин)
- GitHub repo: `Yen66/cs2-faceit-bot`
