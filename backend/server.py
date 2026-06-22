"""
Waifu Tap — Backend API (aiohttp сервер)
"""
import asyncio
import json
import hmac
import hashlib
import os
import sys
from datetime import datetime

from aiohttp import web

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from backend.database import *

routes = web.RouteTableDef()


# ─── Валидация Telegram WebApp данных ───

def validate_telegram_data(init_data: str) -> dict | None:
    """Проверяет подпись WebApp данных через HMAC-SHA256"""
    try:
        from urllib.parse import parse_qs
        parsed = parse_qs(init_data)
        data_dict = {k: v[0] for k, v in parsed.items()}

        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            return None

        sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

        secret_key = hmac.new(
            b"WebAppData",
            config.BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if received_hash != expected_hash:
            return None

        if "user" in data_dict:
            data_dict["user"] = json.loads(data_dict["user"])

        return data_dict
    except Exception as e:
        print(f"[Auth Error] {e}")
        return None


# ─── CORS middleware ───

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            }
        )
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ─── API Routes ───

@routes.post("/api/auth")
async def auth(request):
    """Авторизация пользователя через Telegram WebApp"""
    try:
        body = await request.json()
        init_data = body.get("initData", "")
        referrer_id = body.get("referrerId")

        validated = validate_telegram_data(init_data)
        if not validated:
            return web.json_response({"success": False, "error": "Invalid auth data"}, status=401)

        user_data = validated["user"]
        telegram_id = user_data["id"]
        first_name = user_data.get("first_name", "")
        username = user_data.get("username", "")

        user = await get_or_create_user(telegram_id, first_name, username, referrer_id)

        return web.json_response({"success": True, "user": user})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/user/{telegram_id}")
async def get_user(request):
    """Получить данные пользователя"""
    telegram_id = int(request.match_info["telegram_id"])
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return web.json_response({"success": False, "error": "User not found"}, status=404)

    safe_user = {k: v for k, v in user.items() if k != "id"}
    return web.json_response({"success": True, "user": safe_user})


@routes.post("/api/tap")
async def tap(request):
    """Обработать тап"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        if not telegram_id:
            return web.json_response({"success": False, "error": "telegram_id required"}, status=400)

        result = await process_tap(telegram_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.post("/api/tap/batch")
async def tap_batch(request):
    """Обработать пачку тапов (для автотапа)"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        count = min(int(body.get("count", 1)), 50)

        if not telegram_id:
            return web.json_response({"success": False, "error": "telegram_id required"}, status=400)

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

        return web.json_response({
            "success": True,
            "taps": taps_done,
            "total_earned": round(total_earned, 1),
            "energy": energy,
            "max_energy": max_energy,
            "combo": combo
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/shop")
async def shop(request):
    """Получить товары магазина"""
    category = request.query.get("category")
    items = await get_shop_items(category)
    return web.json_response({"success": True, "items": items})


@routes.post("/api/shop/buy")
async def buy(request):
    """Купить предмет"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        item_id = body.get("item_id")
        payment_method = body.get("payment_method", "coins")

        if not telegram_id or not item_id:
            return web.json_response({"success": False, "error": "telegram_id and item_id required"}, status=400)

        result = await buy_item(telegram_id, item_id, payment_method)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/leaderboard")
async def leaderboard(request):
    """Топ пользователей"""
    limit = int(request.query.get("limit", 50))
    top = await get_leaderboard(limit)

    waifus = await get_all_waifus()
    waifu_map = {w["id"]: {"name": w["name"], "emoji": w["emoji"]} for w in waifus}

    result = []
    for i, u in enumerate(top, 1):
        waifu_info = waifu_map.get(u["current_waifu_id"], {"name": "—", "emoji": "🌸"})
        result.append({
            "rank": i,
            "telegram_id": u["telegram_id"],
            "name": u["first_name"] or u["username"] or f"User {u['telegram_id']}",
            "coins": u["coins"],
            "total_taps": u["total_taps"],
            "waifu": waifu_info
        })

    return web.json_response({"success": True, "leaderboard": result})


@routes.post("/api/daily/claim")
async def daily_claim(request):
    """Забрать ежедневную награду"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        if not telegram_id:
            return web.json_response({"success": False, "error": "telegram_id required"}, status=400)

        result = await claim_daily_reward(telegram_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/daily/status/{telegram_id}")
async def daily_status(request):
    """Статус ежедневной награды"""
    telegram_id = int(request.match_info["telegram_id"])
    status = await get_daily_status(telegram_id)
    return web.json_response({"success": True, **status})


@routes.get("/api/inventory/{telegram_id}")
async def user_inventory(request):
    """Инвентарь пользователя"""
    telegram_id = int(request.match_info["telegram_id"])
    items = await get_user_inventory(telegram_id)
    return web.json_response({"success": True, "inventory": items})


@routes.get("/api/waifus")
async def waifus(request):
    """Список всех вайфу"""
    all_waifus = await get_all_waifus()
    return web.json_response({"success": True, "waifus": all_waifus})


@routes.post("/api/waifu/select")
async def select_waifu(request):
    """Выбрать/купить вайфу"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        waifu_id = body.get("waifu_id")

        if not telegram_id or not waifu_id:
            return web.json_response({"success": False, "error": "telegram_id and waifu_id required"}, status=400)

        result = await waifu_unlock(telegram_id, waifu_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/referral/{telegram_id}")
async def referral_info(request):
    """Реферальная информация"""
    telegram_id = int(request.match_info["telegram_id"])
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return web.json_response({"success": False, "error": "User not found"}, status=404)

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user["id"],)
        )
        referral_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT SUM(bonus_coins) FROM referrals WHERE referrer_id = ?",
            (user["id"],)
        )
        total_bonus = (await cursor.fetchone())[0] or 0

        return web.json_response({
            "success": True,
            "referral_count": referral_count,
            "total_bonus": total_bonus,
            "referral_link": f"https://t.me/{config.BOT_USERNAME}?start=ref_{telegram_id}"
        })
    finally:
        await db.close()


# ─── ADMIN API ───

def check_admin(request) -> bool:
    """Проверить, что запрос от админа"""
    admin_id = request.headers.get("X-Admin-Id")
    return admin_id and int(admin_id) == config.ADMIN_ID


@routes.post("/api/admin/addcoins")
async def admin_addcoins(request):
    """Админ: начислить монеты"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id")
        if admin_id != config.ADMIN_ID:
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        telegram_id = body.get("telegram_id")
        amount = float(body.get("amount", 0))

        if amount <= 0:
            return web.json_response({"success": False, "error": "Amount must be positive"})

        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return web.json_response({"success": False, "error": "User not found"})

        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET coins = coins + ?, total_coins_earned = total_coins_earned + ? WHERE id = ?",
                (amount, amount, user["id"])
            )
            await db.execute(
                """INSERT INTO transactions (user_id, type, amount, currency, description)
                VALUES (?, 'admin_gift', ?, 'coins', 'Начислено администратором')""",
                (user["id"], amount)
            )
            await db.commit()
        finally:
            await db.close()

        return web.json_response({"success": True, "new_balance": user["coins"] + amount})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.post("/api/admin/addstars")
async def admin_addstars(request):
    """Админ: начислить Stars"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id")
        if admin_id != config.ADMIN_ID:
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        telegram_id = body.get("telegram_id")
        amount = int(body.get("amount", 0))

        if amount <= 0:
            return web.json_response({"success": False, "error": "Amount must be positive"})

        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return web.json_response({"success": False, "error": "User not found"})

        db = await get_db()
        try:
            await db.execute(
                "UPDATE users SET stars = stars + ?, total_stars_earned = total_stars_earned + ? WHERE id = ?",
                (amount, amount, user["id"])
            )
            await db.execute(
                """INSERT INTO transactions (user_id, type, amount, currency, description)
                VALUES (?, 'admin_gift', ?, 'stars', 'Начислено администратором')""",
                (user["id"], amount)
            )
            await db.commit()
        finally:
            await db.close()

        return web.json_response({"success": True, "new_balance": user["stars"] + amount})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/api/admin/stats")
async def admin_stats(request):
    """Админ: статистика бота"""
    admin_id = request.query.get("admin_id")
    if int(admin_id or 0) != config.ADMIN_ID:
        return web.json_response({"success": False, "error": "Access denied"}, status=403)

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

        return web.json_response({
            "success": True,
            "stats": {
                "total_users": total_users,
                "total_coins": total_coins,
                "total_taps": total_taps,
                "total_stars": total_stars,
                "total_referrals": total_referrals,
                "active_today": active_today,
                "active_week": active_week,
            }
        })
    finally:
        await db.close()


@routes.post("/api/admin/broadcast")
async def admin_broadcast(request):
    """Админ: рассылка (заглушка — реальная рассылка в боте)"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id")
        if admin_id != config.ADMIN_ID:
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        text = body.get("text", "")

        # Сохраняем сообщение для рассылки
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total = (await cursor.fetchone())[0]

            # В реальности тут будет очередь рассылки
            # Пока просто логируем
            print(f"[BROADCAST] Admin {admin_id}: {text[:50]}... to {total} users")

            return web.json_response({
                "success": True,
                "sent": total,
                "message": "Рассылка запущена. В продакшене добавить очередь."
            })
        finally:
            await db.close()
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


# ─── DEV / GUEST AUTH (для теста в браузере) ───

@routes.post("/api/guest/auth")
async def guest_auth(request):
    """Авторизация для локального теста без Telegram"""
    try:
        body = await request.json()
        guest_id = body.get("guest_id", "")
        name = body.get("name", "Гость")

        # Используем guest_id как telegram_id (в разработке)
        import hashlib
        telegram_id = int(hashlib.md5(guest_id.encode()).hexdigest()[:8], 16)

        user = await get_or_create_user(telegram_id, name, f"guest_{guest_id[:8]}")

        # Даём стартовые монеты и энергию для теста
        if user["coins"] == 0:
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE users SET coins = 5000, max_energy = 500, energy = 500, energy_regen_level = 2 WHERE id = ?",
                    (user["id"],)
                )
                await db.commit()
                user["coins"] = 5000
                user["max_energy"] = 500
                user["energy"] = 500
                user["energy_regen_level"] = 2
            finally:
                await db.close()

        return web.json_response({"success": True, "user": user, "is_guest": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


@routes.get("/health")
async def health(request):
    return web.json_response({"status": "ok", "time": datetime.utcnow().isoformat()})


# ─── Статика для фронтенда ───

async def handle_frontend(request):
    """Отдаёт index.html для Mini App"""
    frontend_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "index.html"
    )
    if os.path.exists(frontend_path):
        return web.FileResponse(frontend_path)
    return web.json_response({"error": "Frontend not found"}, status=404)


# ─── Создание приложения ───

async def create_app():
    """Создать и настроить aiohttp приложение"""
    init_db_path(config.DB_PATH)
    await init_db()

    app = web.Application(middlewares=[cors_middleware])

    # API маршруты
    app.add_routes(routes)

    # Фронтенд
    frontend_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend"
    )
    app.router.add_get("/", handle_frontend)
    app.router.add_static("/assets",
                          os.path.join(frontend_dir, "assets"),
                          name="assets")

    return app


async def run_server(host=None, port=None, block=False):
    app = await create_app()
    host = host or config.HOST
    port = port or int(os.getenv("PORT", config.PORT))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    print(f"\033[38;5;213m🚀 Waifu Tap API на http://{host}:{port}\033[0m")
    print(f"\033[38;5;213m📱 Mini App: http://{host}:{port}/\033[0m")
    await site.start()

    if block:
        # Бесконечное ожидание (работает в nohup/фоне)
        stop_event = asyncio.Event()
        try:
            import signal
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda: stop_event.set())
                except NotImplementedError:
                    pass
        except (ImportError, AttributeError):
            pass
        await stop_event.wait()
        await runner.cleanup()

    return runner


def main():
    asyncio.run(run_server(block=True))


if __name__ == "__main__":
    main()
