#!/bin/bash
# Waifu Tap — Запуск проекта
# Usage: ./run.sh [server|bot|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета
PINK='\033[38;5;213m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${PINK}"
echo "╔══════════════════════════════════╗"
echo "║       🌸 Waifu Tap 🌸           ║"
echo "║   Тыкай свою вайфу!              ║"
echo "╚══════════════════════════════════╝"
echo -e "${NC}"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден. Установи: sudo pacman -S python${NC}"
    exit 1
fi

# Создание data директории
mkdir -p data

# Установка зависимостей
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${YELLOW}📦 Создаю виртуальное окружение...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}📦 Устанавливаю зависимости...${NC}"
    pip install -q -r requirements.txt
fi

# Проверка конфига
if grep -q "ВАШ_ТОКЕН_БОТА" config.py; then
    echo -e "${RED}⚠️  ВНИМАНИЕ: Не настроен BOT_TOKEN в config.py!${NC}"
    echo -e "${RED}   Отредактируй config.py и укажи токен бота${NC}"
    echo ""
fi

if grep -q "ваш-домен.com" config.py; then
    echo -e "${YELLOW}⚠️  WEBAPP_URL не настроен. Для локального теста используй ngrok.${NC}"
    echo -e "${YELLOW}   Или поставь WEBAPP_URL = 'http://localhost:8000' для теста${NC}"
    echo ""
fi

case "${1:-all}" in
    server)
        echo -e "${GREEN}🚀 Запускаю Backend сервер...${NC}"
        python3 backend/server.py
        ;;
    bot)
        echo -e "${GREEN}🤖 Запускаю Telegram бота...${NC}"
        python3 bot/main.py
        ;;
    all)
        echo -e "${GREEN}🚀 Запускаю Backend сервер + Telegram бота...${NC}"
        echo ""
        
        # Запускаем сервер в фоне
        python3 backend/server.py &
        SERVER_PID=$!
        echo -e "${GREEN}📡 Backend PID: $SERVER_PID${NC}"
        
        # Небольшая пауза для старта сервера
        sleep 2
        
        # Запускаем бота
        python3 bot/main.py &
        BOT_PID=$!
        echo -e "${GREEN}🤖 Bot PID: $BOT_PID${NC}"
        
        echo ""
        echo -e "${PINK}══════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ Waifu Tap запущен!${NC}"
        echo -e "${PINK}📱 Mini App: http://localhost:8000${NC}"
        echo -e "${PINK}📡 API:      http://localhost:8000/api/auth${NC}"
        echo -e "${PINK}🤖 Bot:      https://t.me/твой_бот${NC}"
        echo -e "${PINK}══════════════════════════════════════${NC}"
        echo -e "${YELLOW}Нажми Ctrl+C для остановки${NC}"
        
        # Ожидание сигнала
        trap "kill $SERVER_PID $BOT_PID 2>/dev/null; exit 0" SIGINT SIGTERM
        wait
        ;;
    *)
        echo -e "${YELLOW}Использование: ./run.sh [server|bot|all]${NC}"
        echo "  server  — только backend API"
        echo "  bot     — только Telegram bot"
        echo "  all     — всё сразу (по умолчанию)"
        exit 1
        ;;
esac
