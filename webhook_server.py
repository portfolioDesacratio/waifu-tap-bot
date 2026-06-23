"""
Waifu Tap — Webhook Server for Render.com
Запускает aiohttp сервер с вебхуком для Telegram бота.
Без удаления вебхука при shutdown, с автоподдержанием активности.
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

# Создаём бота (глобально, живёт весь срок)
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Путь к папке с фронтендом
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

# API бэкенд (alwaysdata)
BACKEND_API = "https://waifutap.alwaysdata.net"

# ─── API Proxy ───

async def api_proxy(request):
    """Проксирует /api/* запросы на alwaysdata (единый origin, без CORS)"""
    import aiohttp
    path = request.match_info.get('path', '')
    qs = request.query_string
    url = f"{BACKEND_API}/api/{path}"
    if qs:
        url += f"?{qs}"
    
    data = None
    if request.method in ('POST', 'PUT', 'PATCH'):
        try:
            data = await request.json()
        except:
            data = await request.read()
    
    headers = {
        'Content-Type': request.content_type or 'application/json',
        'Accept': 'application/json',
    }
    # Пробрасываем заголовки Telegram
    for h in ('X-Admin-Id', 'X-Telegram-Init-Data'):
        if h in request.headers:
            headers[h] = request.headers[h]
    
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method=request.method,
                url=url,
                json=data if isinstance(data, dict) else None,
                data=data if isinstance(data, bytes) else None,
                headers=headers
            ) as resp:
                body = await resp.read()
                return web.Response(
                    status=resp.status,
                    body=body,
                    content_type=resp.content_type or 'application/json',
                    headers={'Access-Control-Allow-Origin': '*'}
                )
    except asyncio.TimeoutError:
        return web.json_response({"success": False, "error": "API timeout"}, status=504)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=502)

# ─── Frontend handler ───

async def index_handler(request):
    """Отдаёт index.html для мини аппа"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return web.FileResponse(index_path)
    return web.Response(text="index.html not found", status=404)

# ─── Webhook handler ───

async def webhook_handler(request):
    """Принимает апдейты от Telegram"""
    try:
        update_data = await request.json()
        uid = update_data.get('update_id', '?')
        has_msg = 'message' in update_data
        has_cb = 'callback_query' in update_data
        logger.info(f"📩 Webhook received: update_id={uid}, message={has_msg}, callback={has_cb}")
        
        update = Update(**update_data)
        await dp.feed_update(bot=bot, update=update)
        logger.info(f"✅ Update {uid} processed successfully")
        
        # Отправляем уведомление админу о получении апдейта
        msg_text = update_data.get('message', {}).get('text', 'non-text')
        try:
            await bot.send_message(
                chat_id=8587090554,
                text=f"📩 Webhook обработал update #{uid}: {msg_text}",
                disable_notification=True
            )
        except Exception as notify_err:
            logger.warning(f"Admin notify failed: {notify_err}")
        
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        # Уведомляем админа об ошибке
        try:
            await bot.send_message(
                chat_id=8587090554,
                text=f"❌ Webhook error on Render:\n<code>{e}</code>",
                parse_mode="HTML",
                disable_notification=True
            )
        except:
            pass
        return web.Response(text="error", status=500)

async def health_handler(request):
    """Healthcheck для Render"""
    return web.json_response({"status": "ok", "service": "waifu-tap-bot"})

# ─── Фоновый keepalive ───

async def keepalive_loop(app):
    """Каждые 10 минут пинает себя, чтобы Render не уснул"""
    while True:
        await asyncio.sleep(600)  # 10 минут
        try:
            # Локальный запрос к себе
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5):
                    pass
            logger.debug("🔄 Keepalive ping")
        except Exception as e:
            logger.warning(f"Keepalive error: {e}")

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

    # Запускаем фоновый keepalive
    app.keepalive_task = asyncio.create_task(keepalive_loop(app))

async def on_shutdown(app):
    """При выключении — НЕ удаляем вебхук, пусть Telegram накапливает апдейты"""
    # Отменяем keepalive, если он есть
    task = getattr(app, 'keepalive_task', None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown — webhook preserved (not deleted)")

# ─── App creation ───

def create_app():
    app = web.Application()
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # POST + GET для обратной совместимости
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/webhook", webhook_handler)
    app.router.add_get("/health", health_handler)
    
    # Статика для мини аппа — на корне
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.router.add_static("/assets", assets_dir, show_index=False)
    app.router.add_get("/", index_handler)
    
    # API прокси — все /api/* → всегдаdata
    app.router.add_route("*", "/api/{path:.*}", api_proxy)
    
    return app

# ─── Entry point ───

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    app = create_app()
    web.run_app(app, host=HOST, port=PORT)
