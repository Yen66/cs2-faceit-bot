#!/bin/bash
# Safe deploy: syntax check, push, force Render deploy, then re-assert webhook.
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

# --- load secrets from .env ---
BOT_TOKEN=$(grep '^BOT_TOKEN=' .env | cut -d= -f2- | tr -d '\r')
RENDER_API_KEY=$(grep '^RENDER_API_KEY=' .env | cut -d= -f2- | tr -d '\r')
RENDER_SERVICE_ID=$(grep '^RENDER_SERVICE_ID=' .env | cut -d= -f2- | tr -d '\r')

# --- explicitly trigger Render deploy (auto-deploy from GitHub is unreliable on this service) ---
if [ -n "$RENDER_API_KEY" ] && [ -n "$RENDER_SERVICE_ID" ]; then
    echo "🚀 Triggering Render deploy..."
    RESP=$(curl -s --max-time 20 -X POST "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys" \
        -H "Authorization: Bearer ${RENDER_API_KEY}" \
        -H "Accept: application/json" || true)
    DEPLOY_ID=$(echo "$RESP" | python -c "import sys,json; d=sys.stdin.read(); print((json.loads(d) if d.strip().startswith(chr(123)) else {}).get('id',''))" 2>/dev/null || echo "")
    if [ -n "$DEPLOY_ID" ]; then
        echo "   deploy id: ${DEPLOY_ID}"
    else
        echo "   (could not parse deploy id, response: ${RESP:0:200}) — deploy may still have triggered"
    fi
else
    echo "⚠️  RENDER_API_KEY / RENDER_SERVICE_ID missing in .env — relying on auto-deploy."
fi

echo "⏳ Waiting 150s for rolling deploy to finish..."
sleep 150

if [ -n "$BOT_TOKEN" ]; then
    echo "🔗 Re-asserting Telegram webhook (safety net)..."
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://cs2-faceit-bot.onrender.com/webhook" > /dev/null
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
    echo ""
fi

echo "✅ Done."
