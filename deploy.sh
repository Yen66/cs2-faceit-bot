#!/bin/bash
# Safe deploy: syntax check, push, then re-assert webhook after Render has spun up.
# Usage: ./deploy.sh "commit message"
set -e

cd "$(dirname "$0")"

echo "🔎 Checking syntax..."
python -m py_compile bot.py handlers/*.py formatters/*.py

git add -A
if git diff --cached --quiet; then
    echo "Nothing to commit."
else
    git commit -m "${1:-update}"
fi
git push

echo "✅ Pushed. Render will auto-deploy."
echo "⏳ Waiting 150s for Render rolling deploy to finish..."
sleep 150

BOT_TOKEN=$(grep '^BOT_TOKEN=' .env | cut -d= -f2-)
if [ -z "$BOT_TOKEN" ]; then
    echo "⚠️  BOT_TOKEN not found in .env — skipping webhook re-assert."
    exit 0
fi

echo "🔗 Re-asserting webhook (idempotent safety net)..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://cs2-faceit-bot.onrender.com/webhook"
echo ""
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
echo ""
echo "✅ Done."
