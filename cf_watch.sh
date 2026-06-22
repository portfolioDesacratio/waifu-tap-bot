#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
while true; do
    if ! pgrep -f "cloudflared tunnel.*8001" > /dev/null; then
        echo "$(date) — Cloudflare tunnel упал, перезапуск..."
        nohup /usr/local/bin/cloudflared tunnel --url http://localhost:8001 \
          --protocol http2 --no-autoupdate \
          > /tmp/cf_tunnel.log 2>&1 &
        sleep 8
        URL=$(grep -oP 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/cf_tunnel.log 2>/dev/null | head -1)
        if [ -n "$URL" ]; then
            sed -i "s|WEBAPP_URL: str = .*|WEBAPP_URL: str = os.getenv(\"WEBAPP_URL\", \"$URL\")|" "$DIR/config.py"
            pkill -f "python3.*bot/main.py" 2>/dev/null
            sleep 1
            cd "$DIR" && python3 bot/main.py > /tmp/w_bot.log 2>&1 &
            echo "$(date) — Восстановлено с URL: $URL"
        fi
    fi
    sleep 30
done
