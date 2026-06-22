"""
Waifu Tap — Production entry point.
Starts both the API server and Telegram bot.
"""
import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config

async def main():
    # Start server (aiohttp) — стартуем и не ждём (фон)
    from backend.server import run_server
    server_task = asyncio.create_task(run_server(
        host=config.HOST,
        port=int(os.getenv("PORT", config.PORT)),
        block=True   # бесконечное ожидание
    ))
    
    logger.info("🚀 Waifu Tap API запущен!")
    
    # Start bot (aiogram) с автоперезапуском
    from bot.main import run_bot
    while True:
        try:
            logger.info("🤖 Запуск Waifu Tap Bot...")
            await run_bot(block=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Бот упал: {e}")
            logger.info("🔄 Перезапуск бота через 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
