"""
Waifu Tap — база данных и модели
"""
import aiosqlite
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from config import config

DB_PATH = None

def init_db_path(path: str):
    global DB_PATH
    DB_PATH = path
    os.makedirs(os.path.dirname(path), exist_ok=True)

async def get_db():
    if not DB_PATH:
        raise RuntimeError("DB_PATH not initialized. Call init_db_path() first.")
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def init_db():
    """Создание всех таблиц при запуске"""
    db = await get_db()
    try:
        # Пользователи
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                coins REAL DEFAULT 0,
                stars INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                max_energy INTEGER DEFAULT 100,
                coins_per_tap REAL DEFAULT 1.0,
                tap_level INTEGER DEFAULT 1,
                auto_tap_enabled INTEGER DEFAULT 0,
                auto_tap_level INTEGER DEFAULT 0,
                auto_tap_interval INTEGER DEFAULT 5,
                energy_regen_level INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_energy_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                referrer_id INTEGER DEFAULT NULL,
                total_coins_earned REAL DEFAULT 0,
                total_taps INTEGER DEFAULT 0,
                current_waifu_id INTEGER DEFAULT 1,
                total_stars_earned INTEGER DEFAULT 0,
                total_stars_spent INTEGER DEFAULT 0,
                tap_combo INTEGER DEFAULT 0,
                last_tap_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT DEFAULT '🌸',
                description TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                gif_url TEXT DEFAULT '',
                price_stars INTEGER DEFAULT 0,
                price_coins REAL DEFAULT 0,
                rarity TEXT DEFAULT 'common',
                is_default INTEGER DEFAULT 0,
                unlock_requirement TEXT DEFAULT ''
            );
            
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                price_coins REAL DEFAULT 0,
                price_stars INTEGER DEFAULT 0,
                item_type TEXT NOT NULL,
                item_value TEXT NOT NULL DEFAULT '{}',
                emoji TEXT DEFAULT '🎁',
                max_purchases INTEGER DEFAULT 0,
                level_required INTEGER DEFAULT 0,
                category TEXT DEFAULT 'boosts',
                sort_order INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES shop_items(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'coins',
                description TEXT DEFAULT '',
                reference_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                bonus_coins REAL DEFAULT 500,
                bonus_claimed INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (referred_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(referred_id)
            );
            
            CREATE TABLE IF NOT EXISTS daily_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                day INTEGER DEFAULT 1,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS owned_waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                waifu_id INTEGER NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (waifu_id) REFERENCES waifus(id) ON DELETE CASCADE,
                UNIQUE(user_id, waifu_id)
            );
            
            CREATE TABLE IF NOT EXISTS user_skins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                skin_name TEXT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, skin_name)
            );
        """)
        
        await db.commit()
        
        # Заполняем вайфу по умолчанию, если таблица пуста
        cursor = await db.execute("SELECT COUNT(*) FROM waifus")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await seed_waifus(db)
            await seed_shop(db)
            await db.commit()
    finally:
        await db.close()

async def seed_waifus(db):
    """Реальные аниме-персонажи"""
    waifus = [
        (1, 'Аска Лэнгли', '🔴', 'Пилот Evangelion. Рыжая, дерзкая, лучшая! +1 монета за тап', 
         '/assets/images/waifu1.svg', '', 0, 0, 'common', 1, ''),
        (2, 'Рей Аянами', '🔵', 'Первый пилот Evangelion. Загадочная и спокойная. +2 к энергии', 
         '/assets/images/waifu2.svg', '', 50, 25000, 'rare', 0, 'tap_level >= 5'),
        (3, 'Пауэр', '🩸', 'Охотница на демонов из CSM. Безумная и весёлая! x2 монеты за тап', 
         '/assets/images/waifu3.svg', '', 100, 50000, 'epic', 0, 'total_taps >= 500'),
        (4, 'Макима', '🦊', 'Контролёр демонов из CSM. Таинственная и опасная. +50 макс энергии', 
         '/assets/images/waifu4.svg', '', 200, 100000, 'legendary', 0, 'total_coins_earned >= 50000'),
        (5, 'Рукия Кучики', '⚔️', 'Шиннигами из Bleach. Мастер меча. x3 монеты за тап', 
         '/assets/images/waifu5.svg', '', 300, 200000, 'legendary', 0, 'total_taps >= 5000'),
        (6, 'Йор Брайар', '🗡️', 'Киллер из Spy×Family. Элегантная и смертоносная. +100 макс энергии', 
         '/assets/images/waifu6.svg', '', 400, 350000, 'epic', 0, 'tap_level >= 15'),
        (7, 'Зеро Цвай', '👹', 'Пилот Franxx. С рожками и характером. x5 монеты за тап', 
         '/assets/images/waifu7.svg', '', 500, 500000, 'mythic', 0, 'total_taps >= 10000'),
        (8, 'Фрирен', '🧙', 'Маг-эльф из Sousou no Frieren. Мудрая и древняя. +5 авто-тапов', 
         '/assets/images/waifu8.svg', '', 1000, 999999, 'mythic', 0, 'referrals >= 5'),
    ]
    await db.executemany(
        "INSERT INTO waifus (id, name, emoji, description, image_url, gif_url, price_stars, price_coins, rarity, is_default, unlock_requirement) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        waifus
    )

async def seed_shop(db):
    """Магазин предметов"""
    items = [
        # Бусты тапа
        (1, 'Усиление тапа I', 'x2 монет за каждый тап', 1000, 0, 'boost', '{"type": "coins_per_tap", "value": 2}', '👆', 3, 0, 'boosts', 1),
        (2, 'Усиление тапа II', 'x3 монет за каждый тап', 5000, 1, 'boost', '{"type": "coins_per_tap", "value": 3}', '👆', 2, 0, 'boosts', 2),
        (3, 'Усиление тапа III', 'x5 монет за каждый тап', 25000, 5, 'boost', '{"type": "coins_per_tap", "value": 5}', '👆', 1, 0, 'boosts', 3),
        
        # Восполнение энергии
        (4, 'Восполнение энергии', 'Мгновенно восстанавливает всю энергию', 500, 0, 'energy_refill', '{"type": "energy_refill", "value": 100}', '⚡', 0, 0, 'energy', 4),
        
        # Постоянные энерго-ядра (+к макс энергии навсегда)
        (5, 'Энерго-ядро I', 'Постоянно +25 к макс энергии', 2000, 1, 'max_energy', '{"type": "max_energy", "value": 25}', '💎', 5, 0, 'energy', 5),
        (6, 'Энерго-ядро II', 'Постоянно +50 к макс энергии', 5000, 3, 'max_energy', '{"type": "max_energy", "value": 50}', '💎', 3, 0, 'energy', 6),
        (7, 'Энерго-ядро III', 'Постоянно +100 к макс энергии', 15000, 10, 'max_energy', '{"type": "max_energy", "value": 100}', '💎', 2, 0, 'energy', 7),
        (8, 'Энерго-ядро MAX', 'Постоянно +250 к макс энергии', 35000, 20, 'max_energy', '{"type": "max_energy", "value": 250}', '💠', 1, 0, 'energy', 8),
        
        # Авто-тап
        (9, 'Автокликер I', 'Автоматически тапает раз в 5 секунд', 5000, 3, 'auto_tap', '{"type": "auto_tap", "level": 1, "interval": 5}', '🤖', 1, 0, 'auto', 9),
        (10, 'Автокликер II', 'Автоматически тапает раз в 3 секунды', 15000, 10, 'auto_tap', '{"type": "auto_tap", "level": 2, "interval": 3}', '🤖', 1, 0, 'auto', 10),
        (11, 'Автокликер III', 'Автоматически тапает раз в 1 секунду', 50000, 25, 'auto_tap', '{"type": "auto_tap", "level": 3, "interval": 1}', '🤖', 1, 0, 'auto', 11),
        
        # Постоянная регенерация
        (12, 'Ускорение регена I', 'Энергия восстанавливается навсегда ×2 быстрее', 3000, 2, 'energy_regen', '{"type": "energy_regen", "level": 2}', '🔄', 1, 0, 'energy', 12),
        (13, 'Ускорение регена II', 'Энергия восстанавливается навсегда ×3 быстрее', 8000, 5, 'energy_regen', '{"type": "energy_regen", "level": 3}', '🔄', 1, 0, 'energy', 13),
        
        # Временные множители
        (14, 'Удача вайфу (15 мин)', 'x2 ко всем монетам на 15 минут', 3000, 2, 'temporary_boost', '{"type": "profit_multiplier", "value": 2, "duration": 900}', '🍀', 0, 0, 'boosts', 14),
        (15, 'Благословение', 'x3 ко всем монетам на 30 минут', 10000, 8, 'temporary_boost', '{"type": "profit_multiplier", "value": 3, "duration": 1800}', '🌟', 0, 0, 'boosts', 15),
        
        # Скины — теперь на ЛЮБУЮ вайфу (waifu_id=0 = универсальный)
        (16, 'Летнее платье', 'Скин для любой вайфу — летнее платье', 0, 15, 'skin', '{"type": "skin", "name": "summer_dress", "label": "🌺 Летнее платье"}', '👗', 1, 0, 'skins', 16),
        (17, 'Кимоно', 'Скин для любой вайфу — кимоно', 0, 30, 'skin', '{"type": "skin", "name": "kimono", "label": "🎎 Кимоно"}', '🎎', 1, 0, 'skins', 17),
        (18, 'Школьная форма', 'Скин для любой вайфу — школьная форма', 0, 20, 'skin', '{"type": "skin", "name": "school", "label": "📚 Школьная форма"}', '📚', 1, 0, 'skins', 18),
        
        # Пакеты монет
        (19, '1000 монет', 'Пополнение кошелька монетами', 0, 1, 'coins_pack', '{"type": "coins", "value": 1000}', '🪙', 0, 0, 'specials', 19),
        (20, '10000 монет', 'Большой пакет монет', 0, 8, 'coins_pack', '{"type": "coins", "value": 10000}', '💰', 0, 0, 'specials', 20),
        (21, '100000 монет', 'Мега-пакет монет', 0, 70, 'coins_pack', '{"type": "coins", "value": 100000}', '💎', 0, 0, 'specials', 21),
    ]
    await db.executemany(
        """INSERT INTO shop_items 
        (id, name, description, price_coins, price_stars, item_type, item_value, emoji, max_purchases, level_required, category, sort_order)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        items
    )

# ─── User operations ───

async def get_or_create_user(telegram_id: int, first_name: str = "", username: str = "", referrer_id: Optional[int] = None):
    """Получить или создать пользователя"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        
        if user:
            # Обновляем имя/юзернейм
            await db.execute(
                "UPDATE users SET first_name = ?, username = ?, last_activity = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (first_name, username, telegram_id)
            )
            await db.commit()
            user = dict(user)
        else:
            # Создаём нового
            cursor = await db.execute(
                """INSERT INTO users (telegram_id, first_name, username, energy, max_energy, referrer_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (telegram_id, first_name, username, 100, config.BASE_ENERGY, referrer_id)
            )
            await db.commit()
            
            # Бонус рефереру
            if referrer_id:
                # Находим реферера
                ref_cursor = await db.execute("SELECT id FROM users WHERE telegram_id = ?", (referrer_id,))
                ref_user = await ref_cursor.fetchone()
                if ref_user:
                    # Считаем сколько уже пригласил
                    cnt_cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (ref_user["id"],))
                    ref_count = (await cnt_cursor.fetchone())[0]
                    bonus = 5000 + (ref_count * 1000)
                    await db.execute(
                        "INSERT INTO referrals (referrer_id, referred_id, bonus_coins) VALUES (?, ?, ?)",
                        (ref_user["id"], user["id"], bonus)
                    )
                    await db.execute(
                        "UPDATE users SET coins = coins + ? WHERE id = ?",
                        (bonus, ref_user["id"])
                    )
                await db.commit()
            
            user = await get_user_by_telegram_id(telegram_id)
        
        return user
    finally:
        await db.close()

async def get_user_by_telegram_id(telegram_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def update_energy(user_id: int):
    """Обновить энергию пользователя (пассивная регенерация)"""
    db = await get_db()
    try:
        user = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = await user.fetchone()
        if not user:
            return
        
        now = datetime.utcnow()
        last_update = datetime.fromisoformat(user["last_energy_update"])
        seconds_passed = (now - last_update).total_seconds()
        
        if seconds_passed > 0:
            regen_rate = config.ENERGY_REGEN_RATE
            # Check if user has energy regen boost
            if user["energy_regen_level"] > 1:
                regen_rate *= user["energy_regen_level"]
            
            energy_gain = int(seconds_passed / config.ENERGY_REGEN_INTERVAL * regen_rate)
            if energy_gain > 0:
                new_energy = min(user["max_energy"], user["energy"] + energy_gain)
                await db.execute(
                    "UPDATE users SET energy = ?, last_energy_update = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_energy, user_id)
                )
                await db.commit()
    finally:
        await db.close()

async def process_tap(telegram_id: int) -> dict:
    """Обработать тап пользователя"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Обновляем энергию
        await update_energy(user["id"])
        user = await get_user_by_telegram_id(telegram_id)
        
        if user["energy"] < 1:
            # Проверяем комбо
            return {
                "success": False, 
                "error": "no_energy", 
                "energy": 0,
                "max_energy": user["max_energy"]
            }
        
        # Рассчитываем награду
        coins_earned = user["coins_per_tap"]
        
        # Множитель от текущей вайфу
        waifu_bonus = WAIFU_BONUSES.get(user["current_waifu_id"], WAIFU_BONUSES[1])
        coins_earned *= waifu_bonus["tap_multiplier"]
        
        # Проверяем активные временные бусты
        # (в реальном приложении нужно проверять inventory)
        
        # Обновляем пользователя
        new_energy = user["energy"] - 1
        new_total_taps = user["total_taps"] + 1
        new_total_coins = user["total_coins_earned"] + coins_earned
        new_coins = user["coins"] + coins_earned
        
        # Комбо (последовательные тапы без паузы > 2 сек)
        from datetime import datetime
        now = datetime.utcnow()
        last_tap = datetime.fromisoformat(user["last_tap_time"])
        combo = user["tap_combo"]
        
        if (now - last_tap).total_seconds() < 2:
            combo += 1
        else:
            combo = 0
        
        # Бонус за комбо
        combo_bonus = 0
        if combo >= 10:
            combo_bonus = coins_earned * 0.1  # +10%
        if combo >= 25:
            combo_bonus = coins_earned * 0.25  # +25%
        if combo >= 50:
            combo_bonus = coins_earned * 0.5  # +50%
        if combo >= 100:
            combo_bonus = coins_earned * 1.0  # +100%
        
        if combo_bonus > 0:
            combo_bonus = round(combo_bonus, 1)
            new_coins += combo_bonus
            new_total_coins += combo_bonus
        
        await db.execute(
            """UPDATE users SET 
                energy = ?, coins = ?, total_taps = ?, total_coins_earned = ?,
                tap_combo = ?, last_tap_time = CURRENT_TIMESTAMP,
                last_activity = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (new_energy, new_coins, new_total_taps, new_total_coins, combo, user["id"])
        )
        await db.commit()
        
        return {
            "success": True,
            "coins_earned": round(coins_earned + combo_bonus, 1),
            "base_earned": round(coins_earned, 1),
            "combo_bonus": round(combo_bonus, 1),
            "combo": combo,
            "energy": new_energy,
            "max_energy": user["max_energy"],
            "total_coins": round(new_coins, 1),
            "total_taps": new_total_taps
        }
    finally:
        await db.close()

async def buy_item(telegram_id: int, item_id: int, payment_method: str = "coins") -> dict:
    """Купить предмет из магазина"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        cursor = await db.execute("SELECT * FROM shop_items WHERE id = ?", (item_id,))
        item = await cursor.fetchone()
        if not item:
            return {"success": False, "error": "Item not found"}
        
        item = dict(item)
        
        # Проверка лимита покупок
        if item["max_purchases"] > 0:
            cursor = await db.execute(
                "SELECT SUM(quantity) FROM user_inventory WHERE user_id = ? AND item_id = ?",
                (user["id"], item_id)
            )
            total_purchased = (await cursor.fetchone())[0] or 0
            if total_purchased >= item["max_purchases"]:
                return {"success": False, "error": "Лимит покупок исчерпан"}
        
        if payment_method == "coins":
            price = item["price_coins"]
            if user["coins"] < price:
                return {"success": False, "error": "Недостаточно монет", "price": price, "balance": user["coins"]}
            
            # Списываем монеты
            await db.execute(
                "UPDATE users SET coins = coins - ? WHERE id = ?",
                (price, user["id"])
            )
            
        elif payment_method == "stars":
            price = item["price_stars"]
            if user["stars"] < price:
                return {"success": False, "error": "Недостаточно Stars", "price": price, "balance": user["stars"]}
            
            await db.execute(
                "UPDATE users SET stars = stars - ?, total_stars_spent = total_stars_spent + ? WHERE id = ?",
                (price, price, user["id"])
            )
        else:
            return {"success": False, "error": "Unknown payment method"}
        
        # Применяем эффект предмета
        item_value = json.loads(item["item_value"]) if isinstance(item["item_value"], str) else item["item_value"]
        item_type = item["item_type"]
        
        if item_type == "energy_refill":
            # Мгновенное восполнение энергии
            energy_to_add = item_value.get("value", 100)
            new_energy = min(user["max_energy"], user["energy"] + energy_to_add)
            await db.execute(
                "UPDATE users SET energy = ? WHERE id = ?",
                (new_energy, user["id"])
            )
            
        elif item_type == "max_energy":
            # Увеличение макс энергии
            energy_boost = item_value.get("value", 25)
            await db.execute(
                "UPDATE users SET max_energy = max_energy + ? WHERE id = ?",
                (energy_boost, user["id"])
            )
            
        elif item_type == "coins_pack":
            # Пакет монет
            coins_value = item_value.get("value", 1000)
            await db.execute(
                "UPDATE users SET coins = coins + ?, total_coins_earned = total_coins_earned + ? WHERE id = ?",
                (coins_value, coins_value, user["id"])
            )
        
        # Добавляем в инвентарь (для бустов/скинов)
        if item_type in ("boost", "auto_tap", "energy_regen", "temporary_boost"):
            # Проверяем, есть ли уже такой предмет
            cursor = await db.execute(
                "SELECT id, quantity FROM user_inventory WHERE user_id = ? AND item_id = ?",
                (user["id"], item_id)
            )
            existing = await cursor.fetchone()
            if existing:
                await db.execute(
                    "UPDATE user_inventory SET quantity = quantity + 1 WHERE id = ?",
                    (existing["id"],)
                )
            else:
                await db.execute(
                    "INSERT INTO user_inventory (user_id, item_id, quantity, is_active) VALUES (?, ?, 1, 0)",
                    (user["id"], item_id)
                )
            
            # Для auto_tap и energy_regen сразу активируем
            if item_type == "auto_tap":
                await db.execute(
                    "UPDATE users SET auto_tap_enabled = 1, auto_tap_level = ?, auto_tap_interval = ? WHERE id = ?",
                    (item_value.get("level", 1), item_value.get("interval", 5), user["id"])
                )
            elif item_type == "energy_regen":
                await db.execute(
                    "UPDATE users SET energy_regen_level = ? WHERE id = ?",
                    (item_value.get("level", 2), user["id"])
                )
            elif item_type == "boost":
                # Для бустов тапа обновляем coins_per_tap
                boost_mult = item_value.get("value", 2)
                await db.execute(
                    "UPDATE users SET coins_per_tap = coins_per_tap * ? WHERE id = ?",
                    (boost_mult / 2, user["id"])  # хитрость: boost I = x2, поэтому делим на 2
                )
        
        # Скины — в отдельную таблицу wardrobe
        if item_type == "skin":
            skin_name = item_value.get("name", "unknown")
            # Проверяем, есть ли уже
            cursor = await db.execute(
                "SELECT id FROM user_skins WHERE user_id = ? AND skin_name = ?",
                (user["id"], skin_name)
            )
            existing_skin = await cursor.fetchone()
            if not existing_skin:
                await db.execute(
                    "INSERT INTO user_skins (user_id, skin_name, is_active) VALUES (?, ?, 1)",
                    (user["id"], skin_name)
                )
            else:
                # Включаем, если был куплен но выключен
                await db.execute(
                    "UPDATE user_skins SET is_active = 1 WHERE user_id = ? AND skin_name = ?",
                    (user["id"], skin_name)
                )
        
        # Записываем транзакцию
        await db.execute(
            """INSERT INTO transactions (user_id, type, amount, currency, description, reference_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user["id"], f"purchase_{payment_method}", price, payment_method, 
             f"Покупка: {item['name']}", str(item_id))
        )
        
        await db.commit()
        
        # Возвращаем обновлённого пользователя
        updated = await get_user_by_telegram_id(telegram_id)
        return {
            "success": True,
            "item": item["name"],
            "item_emoji": item["emoji"],
            "user": updated
        }
    finally:
        await db.close()

async def get_shop_items(category: Optional[str] = None):
    """Получить список товаров магазина"""
    db = await get_db()
    try:
        if category:
            cursor = await db.execute(
                "SELECT * FROM shop_items WHERE category = ? ORDER BY sort_order",
                (category,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM shop_items ORDER BY category, sort_order"
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

async def get_leaderboard(limit: int = 50):
    """Топ пользователей по монетам"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT telegram_id, first_name, username, coins, total_taps, current_waifu_id 
            FROM users ORDER BY coins DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

async def claim_daily_reward(telegram_id: int) -> dict:
    """Ежедневная награда (с защитой от пропусков)"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Проверяем, получал ли сегодня
        cursor = await db.execute(
            "SELECT COUNT(*) FROM daily_rewards WHERE user_id = ? AND date(claimed_at) = ?",
            (user["id"], today)
        )
        already_claimed = (await cursor.fetchone())[0] > 0
        
        if already_claimed:
            return {"success": False, "error": "already_claimed", "message": "Ты уже получил награду сегодня!"}
        
        # Определяем день с учётом пропусков
        cursor = await db.execute(
            "SELECT day, claimed_at FROM daily_rewards WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 1",
            (user["id"],)
        )
        last = await cursor.fetchone()
        
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        if last is None:
            # Первый раз
            new_day = 1
        else:
            last_claim_date = datetime.fromisoformat(last["claimed_at"]).strftime("%Y-%m-%d")
            if last_claim_date == yesterday or last_claim_date == today:
                # Стрека продолжается (или сегодня уже был, но мы это отсекли выше)
                new_day = min(last["day"] + 1, 7)
            else:
                # Пропуск — сбрасываем на день 1
                new_day = 1
        
        # Награда (новые — крупнее)
        rewards = {
            1: {"coins": 5000, "stars": 0},
            2: {"coins": 7000, "stars": 0},
            3: {"coins": 10000, "stars": 0},
            4: {"coins": 12500, "stars": 1},
            5: {"coins": 15000, "stars": 2},
            6: {"coins": 17500, "stars": 3},
            7: {"coins": 20000, "stars": 5},
        }
        reward = rewards.get(new_day, {"coins": 5000, "stars": 0})
        
        await db.execute(
            "UPDATE users SET coins = coins + ?, stars = stars + ? WHERE id = ?",
            (reward["coins"], reward["stars"], user["id"])
        )
        await db.execute(
            "INSERT INTO daily_rewards (user_id, day) VALUES (?, ?)",
            (user["id"], new_day)
        )
        await db.commit()
        
        return {
            "success": True,
            "day": new_day,
            "coins": reward["coins"],
            "stars": reward["stars"],
            "total_days": new_day
        }
    finally:
        await db.close()

async def get_daily_status(telegram_id: int) -> dict:
    """Статус ежедневной награды (с учётом пропусков)"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"available": False}
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        cursor = await db.execute(
            "SELECT COUNT(*) FROM daily_rewards WHERE user_id = ? AND date(claimed_at) = ?",
            (user["id"], today)
        )
        claimed_today = (await cursor.fetchone())[0] > 0
        
        # Определяем текущий день с учётом пропусков
        cursor = await db.execute(
            "SELECT day, claimed_at FROM daily_rewards WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 1",
            (user["id"],)
        )
        last = await cursor.fetchone()
        
        if last is None:
            current_day = 0
        else:
            last_claim_date = datetime.fromisoformat(last["claimed_at"]).strftime("%Y-%m-%d")
            if last_claim_date == today:
                current_day = last["day"]
            elif last_claim_date == yesterday:
                current_day = last["day"]
            else:
                # Пропуск — сброс
                current_day = 0
        
        next_day = min(current_day + 1, 7)
        
        rewards_map = {
            1: {"coins": 5000, "stars": 0},
            2: {"coins": 7000, "stars": 0},
            3: {"coins": 10000, "stars": 0},
            4: {"coins": 12500, "stars": 1},
            5: {"coins": 15000, "stars": 2},
            6: {"coins": 17500, "stars": 3},
            7: {"coins": 20000, "stars": 5},
        }
        
        return {
            "available": not claimed_today,
            "current_day": current_day,
            "next_day": next_day,
            "claimed_today": claimed_today,
            "rewards": rewards_map
        }
    finally:
        await db.close()

async def get_user_inventory(telegram_id: int):
    """Инвентарь пользователя"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return []
        
        cursor = await db.execute(
            """SELECT si.*, ui.quantity, ui.is_active, ui.purchased_at
            FROM user_inventory ui
            JOIN shop_items si ON ui.item_id = si.id
            WHERE ui.user_id = ?
            ORDER BY ui.purchased_at DESC""",
            (user["id"],)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

async def waifu_unlock(telegram_id: int, waifu_id: int) -> dict:
    """Разблокировать новую вайфу"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        cursor = await db.execute("SELECT * FROM waifus WHERE id = ?", (waifu_id,))
        waifu = await cursor.fetchone()
        if not waifu:
            return {"success": False, "error": "Waifu not found"}
        
        waifu = dict(waifu)
        
        if waifu["price_coins"] > 0 and user["coins"] < waifu["price_coins"]:
            return {"success": False, "error": "Недостаточно монет"}
        if waifu["price_stars"] > 0 and user["stars"] < waifu["price_stars"]:
            return {"success": False, "error": "Недостаточно Stars"}
        
        # Списываем
        await db.execute(
            "UPDATE users SET coins = coins - ?, stars = stars - ? WHERE id = ?",
            (waifu["price_coins"], waifu["price_stars"], user["id"])
        )
        
        # Переключаем
        await db.execute(
            "UPDATE users SET current_waifu_id = ? WHERE id = ?",
            (waifu_id, user["id"])
        )
        
        await db.commit()
        
        return {
            "success": True,
            "waifu": waifu["name"],
            "waifu_emoji": waifu["emoji"]
        }
    finally:
        await db.close()

async def get_user_owned_waifus(user_id: int) -> list[int]:
    """Какие вайфу уже куплены пользователем"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT waifu_id FROM owned_waifus WHERE user_id = ?", (user_id,))
        return [row[0] for row in await cursor.fetchall()]
    finally:
        await db.close()

async def get_all_waifus():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM waifus ORDER BY price_stars ASC, price_coins ASC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ─── Бонусы вайфу (определены в коде) ───
WAIFU_BONUSES = {
    1: {"tap_multiplier": 1,   "max_energy_bonus": 0,   "energy_regen": 0, "auto_taps": 0},  # Аска: базовый
    2: {"tap_multiplier": 1,   "max_energy_bonus": 0,   "energy_regen": 2, "auto_taps": 0},  # Рей: +2 реген
    3: {"tap_multiplier": 2,   "max_energy_bonus": 0,   "energy_regen": 0, "auto_taps": 0},  # Пауэр: x2
    4: {"tap_multiplier": 1,   "max_energy_bonus": 50,  "energy_regen": 0, "auto_taps": 0},  # Макима: +50 макс
    5: {"tap_multiplier": 3,   "max_energy_bonus": 0,   "energy_regen": 0, "auto_taps": 0},  # Рукия: x3
    6: {"tap_multiplier": 1,   "max_energy_bonus": 100, "energy_regen": 0, "auto_taps": 0},  # Йор: +100 макс
    7: {"tap_multiplier": 5,   "max_energy_bonus": 0,   "energy_regen": 0, "auto_taps": 0},  # Зеро: x5
    8: {"tap_multiplier": 1,   "max_energy_bonus": 0,   "energy_regen": 0, "auto_taps": 5},  # Фрирен: +5 автотапов
}

async def clear_all_users():
    """Полностью очистить всех пользователей (для админа)"""
    db = await get_db()
    try:
        await db.executescript("""
            DELETE FROM transactions;
            DELETE FROM referrals;
            DELETE FROM daily_rewards;
            DELETE FROM user_inventory;
            DELETE FROM owned_waifus;
            DELETE FROM user_skins;
            DELETE FROM users;
        """)
        await db.commit()
        return {"success": True, "message": "Все пользователи удалены"}
    finally:
        await db.close()


async def apply_waifu_bonuses(user_id: int, waifu_id: int):
    """Применить бонусы вайфу к пользователю"""
    db = await get_db()
    try:
        bonus = WAIFU_BONUSES.get(waifu_id, WAIFU_BONUSES[1])
        updates = []
        if bonus["max_energy_bonus"] > 0:
            updates.append(f"max_energy = 100 + {bonus['max_energy_bonus']}")
        if bonus["auto_taps"] > 0:
            updates.append(f"auto_tap_level = {bonus['auto_taps']}")
            updates.append("auto_tap_enabled = 1")
        if bonus["energy_regen"] > 0:
            updates.append(f"energy_regen_level = {bonus['energy_regen']}")
        if updates:
            await db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                (user_id,)
            )
            await db.commit()
    finally:
        await db.close()

async def waifu_unlock(telegram_id: int, waifu_id: int) -> dict:
    """Выбрать/купить вайфу"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        cursor = await db.execute("SELECT * FROM waifus WHERE id = ?", (waifu_id,))
        waifu = await cursor.fetchone()
        if not waifu:
            return {"success": False, "error": "Waifu not found"}
        
        waifu = dict(waifu)
        
        # Проверяем, не куплена ли уже
        owned = await get_user_owned_waifus(user["id"])
        already_owned = waifu_id in owned
        
        if not already_owned:
            # Проверяем цену
            if waifu["price_coins"] > 0 and user["coins"] < waifu["price_coins"]:
                return {"success": False, "error": "Недостаточно монет"}
            if waifu["price_stars"] > 0 and user["stars"] < waifu["price_stars"]:
                return {"success": False, "error": "Недостаточно Stars"}
            
            # Списываем
            await db.execute(
                "UPDATE users SET coins = coins - ?, stars = stars - ? WHERE id = ?",
                (waifu["price_coins"], waifu["price_stars"], user["id"])
            )
            
            # Добавляем в коллекцию
            await db.execute(
                "INSERT INTO owned_waifus (user_id, waifu_id) VALUES (?, ?)",
                (user["id"], waifu_id)
            )
        
        # Переключаем на эту вайфу
        await db.execute(
            "UPDATE users SET current_waifu_id = ? WHERE id = ?",
            (waifu_id, user["id"])
        )
        
        # Применяем бонусы
        await apply_waifu_bonuses(user["id"], waifu_id)
        
        await db.commit()
        
        return {
            "success": True,
            "waifu": waifu["name"],
            "waifu_emoji": waifu["emoji"],
            "already_owned": already_owned
        }
    finally:
        await db.close()


# ─── ГАРДЕРОБ (скины) ───

async def get_user_skins(telegram_id: int) -> list:
    """Получить все скины пользователя"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return []
        cursor = await db.execute(
            "SELECT skin_name, is_active, purchased_at FROM user_skins WHERE user_id = ? ORDER BY purchased_at DESC",
            (user["id"],)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()

async def toggle_skin(telegram_id: int, skin_name: str, active: bool) -> dict:
    """Включить/выключить скин"""
    db = await get_db()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        cursor = await db.execute(
            "SELECT id FROM user_skins WHERE user_id = ? AND skin_name = ?",
            (user["id"], skin_name)
        )
        skin = await cursor.fetchone()
        if not skin:
            return {"success": False, "error": "Скин не найден"}
        
        await db.execute(
            "UPDATE user_skins SET is_active = ? WHERE user_id = ? AND skin_name = ?",
            (1 if active else 0, user["id"], skin_name)
        )
        await db.commit()
        return {"success": True, "skin": skin_name, "active": active}
    finally:
        await db.close()


