#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/waifu_start.log"
echo "$(date) — Запуск Waifu Tap..." > "$LOG"

# 1. Сервер
cd "$DIR"
python3 backend/server.py >> "$LOG" 2>&1 &
SERVER_PID=$!
echo "Сервер PID: $SERVER_PID" >> "$LOG"

# 2. Бот
sleep 2
python3 bot/main.py >> "$LOG" 2>&1 &
BOT_PID=$!
echo "Бот PID: $BOT_PID" >> "$LOG"

# 3. Туннель
sleep 2
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
  -R 80:localhost:8001 nokey@localhost.run >> "$LOG" 2>&1 &
TUNNEL_PID=$!
echo "Туннель PID: $TUNNEL_PID" >> "$LOG"

echo "✅ Запущено! Сервер=$SERVER_PID Бот=$BOT_PID Туннель=$TUNNEL_PID" >> "$LOG"
echo "Смотри лог: tail -f $LOG"
