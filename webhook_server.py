"""
Waifu Tap — Webhook Server for Render.com
Встроенный API + вебхук Telegram + статика.
Запускает aiohttp сервер.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

from aiohttp import web

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from aiogram import Bot
from aiogram.types import Update, MenuButtonWebApp, WebAppInfo
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.main import dp, set_commands

# ─── Импорты БД ───
from backend.database import (
    init_db_path, init_db, get_db, get_or_create_user, get_user_by_telegram_id,
    process_tap, get_shop_items, buy_item, get_leaderboard, get_all_waifus,
    waifu_unlock, get_user_owned_waifus, claim_daily_reward, get_daily_status,
    get_user_inventory, get_user_skins, toggle_skin,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Бот ───
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

# ─── Хелпер ───
def json_response(data, status=200):
    return web.json_response(data, status=status, headers={'Access-Control-Allow-Origin': '*'})

def get_json_or_error(request):
    try:
        return request.method in ('POST', 'PUT', 'PATCH'), request.json()
    except:
        return False, None

def validate_telegram_data(init_data: str) -> dict | None:
    try:
        from urllib.parse import parse_qs
        parsed = parse_qs(init_data)
        data_dict = {k: v[0] for k, v in parsed.items()}
        hash_received = data_dict.pop("hash", None)
        if not hash_received:
            return None
        sorted_items = sorted(data_dict.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
        secret_key = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        hash_calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if hash_calculated != hash_received:
            return None
        user_json = data_dict.get("user", "{}")
        return json.loads(user_json)
    except:
        return None

def is_admin(tid):
    return tid and int(tid) == config.ADMIN_ID


# ══════════════════════════════════════════════
# API HANDLERS
# ══════════════════════════════════════════════

async def api_health(request):
    return json_response({"status": "ok", "time": datetime.utcnow().isoformat()})

async def api_auth(request):
    try:
        data = await request.json()
        init_data = data.get("initData", "")
        referrer_id = data.get("referrerId")
        user_data = validate_telegram_data(init_data)
        if not user_data:
            return json_response({"success": False, "error": "Invalid auth data"}, 401)
        telegram_id = user_data.get("id")
        first_name = user_data.get("first_name", "")
        username = user_data.get("username", "")
        user = await get_or_create_user(telegram_id, first_name, username, referrer_id)
        owned = await get_user_owned_waifus(user["id"])
        user["owned_waifus"] = owned
        return json_response({"success": True, "user": user})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_guest_auth(request):
    try:
        data = await request.json()
        guest_id = data.get("guest_id", "guest_unknown")
        name = data.get("name", "Гость")
        telegram_id = int(hashlib.md5(guest_id.encode()).hexdigest()[:8], 16)
        user = await get_or_create_user(telegram_id, name, f"guest_{guest_id[:8]}")
        if user["coins"] == 0:
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE users SET coins = 50000, max_energy = 500, energy = 500, energy_regen_level = 2 WHERE id = ?",
                    (user["id"],)
                )
                await db.commit()
                user["coins"] = 50000
                user["max_energy"] = 500
                user["energy"] = 500
                user["energy_regen_level"] = 2
            finally:
                await db.close()
        owned = await get_user_owned_waifus(user["id"])
        user["owned_waifus"] = owned
        user["guest"] = True
        return json_response({"success": True, "user": user, "is_guest": True})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_bot_register(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        first_name = data.get("first_name", "")
        username = data.get("username", "")
        referrer_id = data.get("referrerId")
        if not telegram_id:
            return json_response({"success": False, "error": "Missing telegram_id"}, 400)
        user = await get_or_create_user(telegram_id, first_name, username, referrer_id)
        owned = await get_user_owned_waifus(user["id"])
        user["owned_waifus"] = owned
        return json_response({"success": True, "user": user})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_user(request):
    telegram_id = int(request.match_info.get('telegram_id', 0))
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return json_response({"success": False, "error": "User not found"}, 404)
    owned = await get_user_owned_waifus(user["id"])
    safe = {k: v for k, v in user.items() if k != "id"}
    safe["owned_waifus"] = owned
    return json_response({"success": True, "user": safe})

async def api_tap(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        if not telegram_id:
            return json_response({"success": False, "error": "telegram_id required"}, 400)
        result = await process_tap(telegram_id)
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_tap_batch(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        count = min(int(data.get("count", 1)), 50)
        if not telegram_id:
            return json_response({"success": False, "error": "telegram_id required"}, 400)
        total_earned = 0
        taps_done = 0
        energy = 0
        max_energy = 100
        combo = 0
        for _ in range(count):
            result = await process_tap(telegram_id)
            if result.get("success"):
                total_earned += result.get("coins_earned", 0)
                taps_done += 1
                energy = result.get("energy", 0)
                max_energy = result.get("max_energy", 100)
                combo = result.get("combo", 0)
            else:
                energy = result.get("energy", 0)
                break
        return json_response({
            "success": True,
            "taps": taps_done,
            "total_earned": round(total_earned, 1),
            "energy": energy,
            "max_energy": max_energy,
            "combo": combo,
        })
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_shop(request):
    category = request.query.get("category")
    items = await get_shop_items(category)
    for item in items:
        if item.get("price_coins", 0) > 0:
            item["price"] = item["price_coins"]
            item["price_type"] = "coins"
        else:
            item["price"] = item["price_stars"]
            item["price_type"] = "stars"
    return json_response({"success": True, "items": items})

async def api_shop_buy(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        item_id = data.get("item_id")
        payment_method = data.get("payment_method", "coins")
        if not telegram_id or not item_id:
            return json_response({"success": False, "error": "telegram_id and item_id required"}, 400)
        result = await buy_item(telegram_id, item_id, payment_method)
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_leaderboard(request):
    limit = int(request.query.get("limit", 50))
    top = await get_leaderboard(limit)
    waifus = await get_all_waifus()
    waifu_map = {w["id"]: {"name": w["name"], "emoji": w["emoji"]} for w in waifus}
    result = []
    for i, u in enumerate(top, 1):
        wi = waifu_map.get(u["current_waifu_id"], {"name": "—", "emoji": "🌸"})
        result.append({
            "rank": i,
            "telegram_id": u["telegram_id"],
            "name": u["first_name"] or u["username"] or f"User {u['telegram_id']}",
            "coins": u["coins"],
            "total_taps": u["total_taps"],
            "waifu": wi,
        })
    return json_response({"success": True, "leaderboard": result})

async def api_daily_claim(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        if not telegram_id:
            return json_response({"success": False, "error": "telegram_id required"}, 400)
        result = await claim_daily_reward(telegram_id)
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_daily_status(request):
    telegram_id = int(request.match_info.get('telegram_id', 0))
    status = await get_daily_status(telegram_id)
    return json_response({"success": True, **status})

async def api_inventory(request):
    telegram_id = int(request.match_info.get('telegram_id', 0))
    items = await get_user_inventory(telegram_id)
    return json_response({"success": True, "inventory": items})

async def api_waifus(request):
    all_w = await get_all_waifus()
    return json_response({"success": True, "waifus": all_w})

async def api_waifu_select(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        waifu_id = data.get("waifu_id")
        if not telegram_id or not waifu_id:
            return json_response({"success": False, "error": "telegram_id and waifu_id required"}, 400)
        result = await waifu_unlock(telegram_id, waifu_id)
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_referral(request):
    telegram_id = int(request.match_info.get('telegram_id', 0))
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return json_response({"success": False, "error": "User not found"}, 404)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user["id"],))
        referral_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(bonus_coins) FROM referrals WHERE referrer_id = ?", (user["id"],))
        total_bonus = (await cursor.fetchone())[0] or 0
        return json_response({
            "success": True,
            "referral_count": referral_count,
            "total_bonus": total_bonus,
            "referral_link": f"https://t.me/{config.BOT_USERNAME}?start=ref_{telegram_id}",
        })
    finally:
        await db.close()

# ─── Скины / Гардероб ───

async def api_skins(request):
    telegram_id = int(request.match_info.get('telegram_id', 0))
    skins = await get_user_skins(telegram_id)
    return json_response({"success": True, "skins": skins})

async def api_skin_toggle(request):
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        skin_name = data.get("skin_name")
        active = data.get("active", False)
        if not telegram_id or not skin_name:
            return json_response({"success": False, "error": "telegram_id and skin_name required"}, 400)
        result = await toggle_skin(telegram_id, skin_name, active)
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

# ─── Admin API ───

async def api_admin_addcoins(request):
    try:
        data = await request.json()
        admin_id = data.get("admin_id")
        if admin_id != config.ADMIN_ID:
            return json_response({"success": False, "error": "Access denied"}, 403)
        telegram_id = data.get("telegram_id")
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return json_response({"success": False, "error": "Amount must be positive"})
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return json_response({"success": False, "error": "User not found"})
        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET coins = coins + ?, total_coins_earned = total_coins_earned + ? WHERE id = ?",
                (amount, amount, user["id"])
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, 'admin_gift', ?, 'coins', 'Начислено администратором')",
                (user["id"], amount)
            )
            await db.commit()
        finally:
            await db.close()
        return json_response({"success": True, "new_balance": user["coins"] + amount})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_admin_addstars(request):
    try:
        data = await request.json()
        admin_id = data.get("admin_id")
        if admin_id != config.ADMIN_ID:
            return json_response({"success": False, "error": "Access denied"}, 403)
        telegram_id = data.get("telegram_id")
        amount = int(data.get("amount", 0))
        if amount <= 0:
            return json_response({"success": False, "error": "Amount must be positive"})
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return json_response({"success": False, "error": "User not found"})
        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET stars = stars + ?, total_stars_earned = total_stars_earned + ? WHERE id = ?",
                (amount, amount, user["id"])
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, 'admin_gift', ?, 'stars', 'Начислено администратором')",
                (user["id"], amount)
            )
            await db.commit()
        finally:
            await db.close()
        return json_response({"success": True, "new_balance": user["stars"] + amount})
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_admin_stats(request):
    try:
        data = await request.json()
        admin_id = data.get("admin_id")
        if int(admin_id or 0) != config.ADMIN_ID:
            return json_response({"success": False, "error": "Access denied"}, 403)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COALESCE(SUM(coins), 0) FROM users")
            total_coins = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COALESCE(SUM(total_taps), 0) FROM users")
            total_taps = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COALESCE(SUM(stars), 0) FROM users")
            total_stars = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM referrals")
            total_referrals = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE last_activity >= datetime('now', '-1 day')")
            active_today = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE last_activity >= datetime('now', '-7 days')")
            active_week = (await cursor.fetchone())[0]
            return json_response({"success": True, "stats": {
                "total_users": total_users, "total_coins": total_coins, "total_taps": total_taps,
                "total_stars": total_stars, "total_referrals": total_referrals,
                "active_today": active_today, "active_week": active_week,
            }})
        finally:
            await db.close()
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)

async def api_admin_clear(request):
    """Очистить всех пользователей (только для админа)"""
    try:
        data = await request.json()
        admin_id = data.get("admin_id")
        if int(admin_id or 0) != config.ADMIN_ID:
            return json_response({"success": False, "error": "Access denied"}, 403)
        from backend.database import clear_all_users
        result = await clear_all_users()
        return json_response(result)
    except Exception as e:
        return json_response({"success": False, "error": str(e)}, 500)


# ══════════════════════════════════════════════
# WEBHOOK + FRONTEND
# ══════════════════════════════════════════════

async def webhook_handler(request):
    try:
        update_data = await request.json()
        uid = update_data.get('update_id', '?')
        has_msg = 'message' in update_data
        has_cb = 'callback_query' in update_data
        logger.info(f"📩 Webhook received: update_id={uid}, message={has_msg}, callback={has_cb}")
        
        update = Update(**update_data)
        await dp.feed_update(bot=bot, update=update)
        logger.info(f"✅ Update {uid} processed successfully")
        
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

async def index_handler(request):
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return web.FileResponse(index_path)
    return web.Response(text="index.html not found", status=404)

async def health_handler(request):
    return web.json_response({"status": "ok", "service": "waifu-tap-bot", "api": "builtin"})

# ─── Keepalive ───

async def keepalive_loop(app):
    while True:
        await asyncio.sleep(600)
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5):
                    pass
            logger.debug("🔄 Keepalive ping")
        except Exception as e:
            logger.warning(f"Keepalive error: {e}")

# ─── Startup / Shutdown ───

async def on_startup(app):
    # Инициализация БД
    db_path = config.DB_PATH
    init_db_path(db_path)
    await init_db()
    logger.info(f"✅ Database initialized: {db_path}")
    
    # Вебхук Telegram
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    if not WEBHOOK_URL:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
        if render_url:
            WEBHOOK_URL = render_url.rstrip("/") + "/webhook"
        else:
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
    
    app.keepalive_task = asyncio.create_task(keepalive_loop(app))

async def on_shutdown(app):
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
    
    # Health
    app.router.add_get("/health", health_handler)
    
    # Вебхук Telegram
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/webhook", webhook_handler)
    
    # Статика
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.router.add_static("/assets", assets_dir, show_index=False)
    app.router.add_get("/", index_handler)
    
    # ─── API ROUTES ───
    # Auth
    app.router.add_post("/api/auth", api_auth)
    app.router.add_post("/api/guest/auth", api_guest_auth)
    app.router.add_post("/api/bot/register", api_bot_register)
    
    # User
    app.router.add_get("/api/user/{telegram_id}", api_user)
    
    # Tap
    app.router.add_post("/api/tap", api_tap)
    app.router.add_post("/api/tap/batch", api_tap_batch)
    
    # Shop
    app.router.add_get("/api/shop", api_shop)
    app.router.add_post("/api/shop/buy", api_shop_buy)
    
    # Daily
    app.router.add_post("/api/daily/claim", api_daily_claim)
    app.router.add_get("/api/daily/status/{telegram_id}", api_daily_status)
    
    # Inventory
    app.router.add_get("/api/inventory/{telegram_id}", api_inventory)
    
    # Waifus
    app.router.add_get("/api/waifus", api_waifus)
    app.router.add_post("/api/waifu/select", api_waifu_select)
    
    # Referral
    app.router.add_get("/api/referral/{telegram_id}", api_referral)
    
    # Leaderboard
    app.router.add_get("/api/leaderboard", api_leaderboard)
    
    # Skins / Wardrobe
    app.router.add_get("/api/skins/{telegram_id}", api_skins)
    app.router.add_post("/api/skin/toggle", api_skin_toggle)
    
    # Admin
    app.router.add_post("/api/admin/addcoins", api_admin_addcoins)
    app.router.add_post("/api/admin/addstars", api_admin_addstars)
    app.router.add_post("/api/admin/stats", api_admin_stats)
    app.router.add_post("/api/admin/clear", api_admin_clear)
    
    return app

# ─── Entry point ───

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    app = create_app()
    web.run_app(app, host=HOST, port=PORT)
