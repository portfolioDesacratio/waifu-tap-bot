#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

while true; do
    echo "$(date) — Запуск cloudflared..."
    
    /usr/local/bin/cloudflared tunnel --url http://localhost:8001 \
      --protocol http2 --no-autoupdate 2>&1 | while read line; do
        
        echo "$line"
        
        # Ловим URL
        URL=$(echo "$line" | grep -oP 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1)
        if [ -n "$URL" ]; then
            echo "$(date) — УРЛ: $URL"
            # Обновляем конфиг и перезапускаем бота
            sed -i "s|WEBAPP_URL: str = .*|WEBAPP_URL: str = os.getenv(\"WEBAPP_URL\", \"$URL\")|" "$DIR/config.py"
            pkill -f "python3.*bot/main.py" 2>/dev/null
            sleep 1
            cd "$DIR" && python3 bot/main.py > /tmp/w_bot.log 2>&1 &
            echo "$(date) — Бот перезапущен"
        fi
        
        # Если соединение упало
        if echo "$line" | grep -q "Connection terminated"; then
            echo "$(date) — Соединение потеряно, переподключаюсь..."
            break  # выходим из while read, чтобы внешний цикл перезапустил
        fi
    done
    
    echo "$(date) — Перезапуск через 5с..."
    sleep 5
done
