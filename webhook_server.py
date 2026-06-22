"""
Waifu Tap — Webhook Server for Render.com
Запускает aiohttp сервер с вебхуком для Telegram бота.
Render будет держать его включённым, пока есть входящие запросы.
"""
import asyncio
import logging
import os
import sys

from aiohttp import web

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from aiogram import Bot
from aiogram.types import Update, MenuButtonWebApp, WebAppInfo
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.main import dp, set_commands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём бота
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# ─── Webhook handler ───

async def webhook_handler(request):
    """Принимает апдейты от Telegram"""
    try:
        update_data = await request.json()
        update = Update(**update_data)
        await dp.feed_update(bot=bot, update=update)
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="error", status=500)

async def health_handler(request):
    return web.json_response({"status": "ok", "service": "waifu-tap-bot"})

# ─── Startup ───

async def on_startup(app):
    """Настраиваем вебхук при старте"""
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    if not WEBHOOK_URL:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if render_url:
            WEBHOOK_URL = render_url.rstrip("/") + "/webhook"
        else:
            # Fallback — принудительно
            WEBHOOK_URL = "https://waifu-tap-bot.onrender.com/webhook"
    
    try:
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logger.info(f"✅ Webhook set: {WEBHOOK_URL}")
    except Exception as e:
        logger.warning(f"⚠️ Webhook failed: {e}")
    
    try:
        await set_commands(bot)
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎮 Waifu Tap",
                web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        )
        logger.info(f"✅ Menu button set: {config.WEBAPP_URL}")
    except Exception as e:
        logger.warning(f"⚠️ Menu/commands setup failed: {e}")

async def on_shutdown(app):
    """Убираем вебхук при выключении"""
    try:
        await bot.delete_webhook()
    except:
        pass

# ─── App creation ───

def create_app():
    app = web.Application()
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    app.router.add_route("*", "/webhook", webhook_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    
    return app

# ─── Entry point ───

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    app = create_app()
    web.run_app(app, host=HOST, port=PORT)
