#!/bin/bash
# Watchdog для localhost.run туннеля
# Запускает туннель и при смене URL обновляет конфиг и перезапускает бота

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

while true; do
    echo "$(date) — Запуск туннеля..."
    
    # Запускаем туннель
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
        -o ExitOnForwardFailure=yes -o ConnectTimeout=20 \
        -R 80:localhost:8001 nokey@localhost.run 2>&1 | while read line; do
        
        echo "$line"
        
        # Перехватываем URL туннеля
        URL=$(echo "$line" | grep -oP 'https://[a-zA-Z0-9-]+\.lhr\.life' | head -1)
        if [ -n "$URL" ]; then
            echo "$(date) — Новый URL: $URL"
            
            # Обновляем config.py
            sed -i "s|WEBAPP_URL: str = .*|WEBAPP_URL: str = os.getenv(\"WEBAPP_URL\", \"$URL\")|" config.py
            echo "$(date) — config.py обновлён"
            
            # Перезапускаем бота
            pkill -f "python3.*bot/main.py" 2>/dev/null
            sleep 1
            cd "$DIR"
            python3 bot/main.py > /tmp/w_bot.log 2>&1 &
            echo "$(date) — Бот перезапущен с URL: $URL"
        fi
    done
    
    echo "$(date) — Туннель упал, перезапуск через 5с..."
    sleep 5
done
