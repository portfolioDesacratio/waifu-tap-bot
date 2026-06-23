"""
Waifu Tap — Telegram Bot (aiogram 3.x)
🌸 Тыкай свою вайфу!
"""
import sys
import os
import asyncio
import logging
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp, BotCommand, BotCommandScopeDefault,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiohttp

from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаём диспетчер без бота (бот — в main)
dp = Dispatcher()


async def safe_delete(message: Message):
    """Безопасно удалить сообщение (не крашится при ошибках)"""
    try:
        await message.delete()
    except Exception:
        pass

# ─── API URL ───
# Бот шлёт запросы на API_URL (локальный сервер или PythonAnywhere)
API_BASE = config.API_URL


async def api_get(endpoint: str, params: dict = None) -> dict:
    """GET запрос к бэкенду"""
    url = f"{API_BASE}{endpoint}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"success": False, "error": f"HTTP {resp.status}"}


async def api_post(endpoint: str, data: dict) -> dict:
    """POST запрос к бэкенду"""
    url = f"{API_BASE}{endpoint}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"success": False, "error": f"HTTP {resp.status}"}


# ─── Команды ───

async def set_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="play", description="🎮 Играть в Waifu Tap"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="shop", description="🛍️ Магазин"),
        BotCommand(command="top", description="🏆 Топ игроков"),
        BotCommand(command="ref", description="🔗 Реферальная ссылка"),
        BotCommand(command="daily", description="🎁 Ежедневная награда"),
        BotCommand(command="admin", description="🔐 Админ-панель"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject = None):
    """Обработка /start"""
    await safe_delete(message)
    user = message.from_user
    args = command.args if command else None

    referrer_id = None
    if args and args.startswith("ref_"):
        try:
            referrer_id = int(args.replace("ref_", ""))
            if referrer_id == user.id:
                referrer_id = None
        except ValueError:
            pass

    # Создаём пользователя через API (бот-регистрация, без Telegram валидации)
    await api_post("/api/bot/register", {
        "telegram_id": user.id,
        "first_name": user.first_name or "",
        "username": user.username or "",
        "referrerId": referrer_id
    })

    welcome_text = """
✨ <b>Добро пожаловать в Waifu Tap!</b> ✨

Тыкай свою вайфу, зарабатывай монеты, открывай новых персонажей и становись лучшим!

<b>🎮 Что тебя ждёт:</b>
• 👆 Тапай по вайфу и зарабатывай монеты
• ⚡ Улучшай энергию и силу тапа
• 🌸 Открывай новых аниме-девочек
• 🏆 Соревнуйся с друзьями в топе
• 🎁 Забирай ежедневные награды
• 💎 Покупай бусты и скины за Stars

<b>👇 Жми кнопку — играть!</b>
    """.strip()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 Играть в Waifu Tap",
            web_app=WebAppInfo(url=config.WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="top")],
        [InlineKeyboardButton(text="🛍️ Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🎁 Daily", callback_data="daily")],
        [InlineKeyboardButton(text="🔗 Пригласить друга", callback_data="ref")]
    ])

    await message.answer(welcome_text, reply_markup=keyboard)

    if referrer_id:
        await message.answer(
            "🎉 Ты пришёл по приглашению! Получи <b>500 монет</b> бонуса!\n"
            "Твой друг тоже получил 500 монет 🤝"
        )


@dp.message(Command("play"))
async def cmd_play(message: Message):
    """Открыть Mini App"""
    await safe_delete(message)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 Открыть Waifu Tap",
            web_app=WebAppInfo(url=config.WEBAPP_URL)
        )]
    ])
    await message.answer(
        "🎮 <b>Нажми кнопку, чтобы начать тапать!</b>\n\n"
        "Тапай по вайфу → зарабатывай монеты → покупай бусты → открывай новых персонажей!",
        reply_markup=keyboard
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    """Показать профиль"""
    await safe_delete(message)
    tg_id = message.from_user.id
    result = await api_get(f"/api/user/{tg_id}")

    if not result.get("success"):
        await message.answer("❌ Ошибка загрузки профиля. Попробуй /start")
        return

    user = result["user"]

    profile_text = f"""
╔══════════════════╗
<b>    👤 Твой профиль</b>
╚══════════════════╝

<b>💰 Монеты:</b> <code>{user['coins']:,.1f}</code>
<b>⭐ Stars:</b> <code>{user['stars']}</code>
<b>👆 Тапов:</b> <code>{user['total_taps']:,}</code>
<b>⚡ Энергия:</b> <code>{user['energy']}/{user['max_energy']}</code>
<b>💪 Сила тапа:</b> <code>{user['coins_per_tap']}x</code>
<b>🤖 Автотап:</b> <code>{'Вкл' if user['auto_tap_enabled'] else 'Выкл'}</code>
<b>🌸 Вайфу:</b> <code>ID {user['current_waifu_id']}</code>
    """.strip()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="🛍️ Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="top")]
    ])

    await message.answer(profile_text, reply_markup=keyboard)


@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    """Ссылка на магазин в Mini App"""
    await safe_delete(message)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛍️ Открыть магазин",
            web_app=WebAppInfo(url=f"{config.WEBAPP_URL}?page=shop")
        )]
    ])
    await message.answer(
        "🛍️ <b>Магазин Waifu Tap</b>\n\n"
        "Тут можно купить:\n"
        "• ⚡ Бусты энергии и силы тапа\n"
        "• 🤖 Автокликеры\n"
        "• 👗 Скины для вайфу\n"
        "• 🌸 Новых персонажей\n"
        "• 💎 Монеты и Stars\n\n"
        "Нажми кнопку, чтобы открыть магазин!",
        reply_markup=keyboard
    )


@dp.message(Command("top"))
async def cmd_top(message: Message):
    """Показать топ-10"""
    await safe_delete(message)
    result = await api_get("/api/leaderboard", {"limit": 15})

    if not result.get("success"):
        await message.answer("❌ Ошибка загрузки топа")
        return

    lb = result["leaderboard"]

    top_text = "<b>🏆 Топ игроков Waifu Tap</b>\n\n"

    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(lb[:15]):
        rank = i + 1
        medal = medals[i] if i < 3 else f"{rank}."
        waifu_emoji = entry.get("waifu", {}).get("emoji", "🌸")
        name = entry["name"]
        if len(name) > 20:
            name = name[:18] + "…"
        coins = entry["coins"]
        top_text += f"{medal} {waifu_emoji} <b>{name}</b> — <code>{coins:,.0f}</code> 🪙\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL)
        )]
    ])

    await message.answer(top_text, reply_markup=keyboard)


@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    """Реферальная ссылка"""
    await safe_delete(message)
    tg_id = message.from_user.id
    me = await message.bot.get_me()
    bot_username = me.username

    ref_link = f"https://t.me/{bot_username}?start=ref_{tg_id}"

    ref_text = f"""
🔗 <b>Твоя реферальная ссылка:</b>

<code>{ref_link}</code>

<b>📌 Как это работает:</b>
• Отправь ссылку другу
• Друг переходит и начинает играть
• Вы оба получаете <b>+500 монет</b> 🪙
• Чем больше друзей — тем больше бонусов!

<b>🔥 Советы:</b>
• Кинь ссылку в чаты про аниме
• Поделись в соцсетях
• Пригласи одноклассников
    """.strip()

    share_url = f"https://t.me/share/url?url={ref_link}&text=🎮 Залетай в Waifu Tap! Тапай вайфу, покупай бусты, открывай персонажей и становись лучшим! 🌸"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=share_url)],
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])

    await message.answer(ref_text, reply_markup=keyboard)


@dp.message(Command("daily"))
async def cmd_daily(message: Message):
    """Ежедневная награда"""
    await safe_delete(message)
    tg_id = message.from_user.id
    result = await api_get(f"/api/daily/status/{tg_id}")

    if not result.get("success"):
        await message.answer("❌ Ошибка")
        return

    status = result

    rewards_info = {
        1: "🎁 5,000 монет",
        2: "🎁 7,000 монет",
        3: "🎁 10,000 монет",
        4: "🎁 12,500 монет + ⭐ 1 Star",
        5: "🎁 15,000 монет + ⭐ 2 Stars",
        6: "🎁 17,500 монет + ⭐ 3 Stars",
        7: "🎁 20,000 монет + ⭐ 5 Stars 👑",
    }

    daily_text = f"""
🎁 <b>Ежедневная награда</b>

День {status['next_day']}/7
    """

    for day_num in range(1, 8):
        reward = rewards_info.get(day_num, "🎁 ???")
        if day_num < status['next_day']:
            daily_text += f"\n✅ День {day_num}: {reward}"
        elif day_num == status['next_day']:
            daily_text += f"\n<b>👉 День {day_num}: {reward} ← ГОТОВО!</b>"
        else:
            daily_text += f"\n🔒 День {day_num}: {reward}"

    daily_text += f"\n\n{'✅ Ты уже получил награду сегодня!' if status['claimed_today'] else '👇 Забери награду!'}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎁 Забрать награду",
            callback_data="claim_daily" if not status['claimed_today'] else "already_claimed"
        )],
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])

    await message.answer(daily_text, reply_markup=keyboard)


# ─── Callback handlers ───

# ─── ADMIN КОМАНДЫ ───

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    text = """
🔐 <b>Админ-панель Waifu Tap</b>

<b>Команды:</b>
• <code>/addcoins user_id amount</code> — начислить монеты
• <code>/addstars user_id amount</code> — начислить Stars
• <code>/stats</code> — статистика бота
• <code>/clear</code> — удалить ВСЕХ пользователей
• <code>/broadcast текст</code> — сообщение всем
• <code>/admin</code> — эта панель
    """.strip()

    await message.answer(text)


@dp.message(Command("addcoins"))
async def cmd_addcoins(message: Message, command: CommandObject):
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    args = command.args.split() if command.args else []
    if len(args) < 2:
        return await message.answer("❌ Использование: /addcoins user_id amount")

    try:
        target_id = int(args[0])
        amount = float(args[1])
    except ValueError:
        return await message.answer("❌ Неверный формат. Пример: /addcoins 123456789 1000")

    # Получаем пользователя из БД через API
    user = await api_get(f"/api/user/{target_id}")
    if not user.get("success"):
        return await message.answer("❌ Пользователь не найден")

    # Добавляем монеты напрямую в БД через API
    result = await api_post("/api/admin/addcoins", {
        "telegram_id": target_id,
        "amount": amount,
        "admin_id": message.from_user.id
    })

    if result.get("success"):
        await message.answer(f"✅ Начислено <b>{amount:,.0f} 🪙</b> пользователю {target_id}")
    else:
        await message.answer("❌ " + result.get("error", "Ошибка"))


@dp.message(Command("addstars"))
async def cmd_addstars(message: Message, command: CommandObject):
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    args = command.args.split() if command.args else []
    if len(args) < 2:
        return await message.answer("❌ Использование: /addstars user_id amount")

    try:
        target_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        return await message.answer("❌ Неверный формат. Пример: /addstars 123456789 5")

    result = await api_post("/api/admin/addstars", {
        "telegram_id": target_id,
        "amount": amount,
        "admin_id": message.from_user.id
    })

    if result.get("success"):
        await message.answer(f"✅ Начислено <b>{amount} ⭐</b> пользователю {target_id}")
    else:
        await message.answer("❌ " + result.get("error", "Ошибка"))


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    result = await api_get("/api/admin/stats", {"admin_id": message.from_user.id})
    if not result.get("success"):
        return await message.answer("❌ Ошибка статистики")

    s = result["stats"]
    text = f"""
📊 <b>Статистика Waifu Tap</b>

👥 Всего пользователей: <code>{s['total_users']}</code>
💰 Всего монет в игре: <code>{s['total_coins']:,.0f}</code>
👆 Всего тапов: <code>{s['total_taps']:,.0f}</code>
⭐ Всего Stars: <code>{s['total_stars']}</code>
🎁 Рефералов: <code>{s['total_referrals']}</code>
    """.strip()

    await message.answer(text)


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject):
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    if not command.args:
        return await message.answer("❌ Напиши текст рассылки: /broadcast Привет всем! 🔥")

    text = command.args
    result = await api_post("/api/admin/broadcast", {
        "text": text,
        "admin_id": message.from_user.id
    })

    if result.get("success"):
        await message.answer(f"✅ Рассылка отправлена <b>{result.get('sent', 0)}</b> пользователям")
    else:
        await message.answer("❌ " + result.get("error", "Ошибка"))


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    """Админ: полностью очистить БД"""
    await safe_delete(message)
    if not is_admin(message.from_user.id):
        return

    # Подтверждение
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_clear")],
        [InlineKeyboardButton(text="⚠️ ДА, удалить всё", callback_data="confirm_clear")]
    ])
    await message.answer(
        "⚠️ <b>Точно удалить ВСЕХ пользователей?</b>\n\n"
        "Будут удалены:\n"
        "• Все пользователи\n"
        "• Все транзакции\n"
        "• Все рефералы\n"
        "• Ежедневные награды\n"
        "• Инвентарь и вайфу\n\n"
        "<b>Это действие необратимо!</b>",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    """Профиль из кнопки"""
    tg_id = callback.from_user.id
    result = await api_get(f"/api/user/{tg_id}")

    if not result.get("success"):
        await callback.message.edit_text("❌ Ошибка загрузки профиля. Попробуй /start")
        await callback.answer()
        return

    user = result["user"]

    profile_text = f"""
╔══════════════════╗
<b>    👤 Твой профиль</b>
╚══════════════════╝

<b>💰 Монеты:</b> <code>{user['coins']:,.1f}</code>
<b>⭐ Stars:</b> <code>{user['stars']}</code>
<b>👆 Тапов:</b> <code>{user['total_taps']:,}</code>
<b>⚡ Энергия:</b> <code>{user['energy']}/{user['max_energy']}</code>
<b>💪 Сила тапа:</b> <code>{user['coins_per_tap']}x</code>
<b>🤖 Автотап:</b> <code>{'Вкл' if user['auto_tap_enabled'] else 'Выкл'}</code>
<b>🌸 Вайфу:</b> <code>ID {user['current_waifu_id']}</code>
    """.strip()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="🛍️ Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="top")]
    ])

    await callback.message.edit_text(profile_text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "top")
async def cb_top(callback: CallbackQuery):
    """Топ из кнопки (редактирует текущее сообщение)"""
    result = await api_get("/api/leaderboard", {"limit": 15})

    if not result.get("success"):
        await callback.message.edit_text("❌ Ошибка загрузки топа")
        await callback.answer()
        return

    lb = result["leaderboard"]
    top_text = "<b>🏆 Топ игроков Waifu Tap</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(lb[:15]):
        rank = i + 1
        medal = medals[i] if i < 3 else f"{rank}."
        waifu_emoji = entry.get("waifu", {}).get("emoji", "🌸")
        name = entry["name"]
        if len(name) > 20:
            name = name[:18] + "…"
        coins = entry["coins"]
        top_text += f"{medal} {waifu_emoji} <b>{name}</b> — <code>{coins:,.0f}</code> 🪙\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])

    await callback.message.edit_text(top_text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    """Магазин из кнопки (редактирует текущее сообщение)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛍️ Открыть магазин",
            web_app=WebAppInfo(url=f"{config.WEBAPP_URL}?page=shop")
        )]
    ])
    await callback.message.edit_text(
        "🛍️ <b>Магазин Waifu Tap</b>\n\n"
        "Тут можно купить:\n"
        "• ⚡ Бусты энергии и силы тапа\n"
        "• 🤖 Автокликеры\n"
        "• 👗 Скины для вайфу\n"
        "• 🌸 Новых персонажей\n"
        "• 💎 Монеты и Stars\n\n"
        "Нажми кнопку, чтобы открыть магазин!",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "daily")
async def cb_daily(callback: CallbackQuery):
    """Ежедневка из кнопки"""
    tg_id = callback.from_user.id
    result = await api_get(f"/api/daily/status/{tg_id}")

    if not result.get("success"):
        await callback.message.edit_text("❌ Ошибка")
        await callback.answer()
        return

    status = result

    rewards_info = {
        1: "🎁 5,000 монет",
        2: "🎁 7,000 монет",
        3: "🎁 10,000 монет",
        4: "🎁 12,500 монет + ⭐ 1 Star",
        5: "🎁 15,000 монет + ⭐ 2 Stars",
        6: "🎁 17,500 монет + ⭐ 3 Stars",
        7: "🎁 20,000 монет + ⭐ 5 Stars 👑",
    }

    daily_text = f"""
🎁 <b>Ежедневная награда</b>

День {status['next_day']}/7
    """

    for day_num in range(1, 8):
        reward = rewards_info.get(day_num, "🎁 ???")
        if day_num < status['next_day']:
            daily_text += f"\n✅ День {day_num}: {reward}"
        elif day_num == status['next_day']:
            daily_text += f"\n<b>👉 День {day_num}: {reward} ← ГОТОВО!</b>"
        else:
            daily_text += f"\n🔒 День {day_num}: {reward}"

    daily_text += f"\n\n{'✅ Ты уже получил награду сегодня!' if status['claimed_today'] else '👇 Забери награду!'}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎁 Забрать награду",
            callback_data="claim_daily" if not status['claimed_today'] else "already_claimed"
        )],
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])

    await callback.message.edit_text(daily_text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "ref")
async def cb_ref(callback: CallbackQuery):
    """Рефералка из кнопки"""
    tg_id = callback.from_user.id
    me = await callback.bot.get_me()
    bot_username = me.username

    ref_link = f"https://t.me/{bot_username}?start=ref_{tg_id}"

    ref_text = f"""
🔗 <b>Твоя реферальная ссылка:</b>

<code>{ref_link}</code>

<b>📌 Как это работает:</b>
• Отправь ссылку другу
• Друг переходит и начинает играть
• Вы оба получаете <b>+500 монет</b> 🪙
• Чем больше друзей — тем больше бонусов!

<b>🔥 Советы:</b>
• Кинь ссылку в чаты про аниме
• Поделись в соцсетях
• Пригласи одноклассников
    """.strip()

    share_url = f"https://t.me/share/url?url={ref_link}&text=🎮 Залетай в Waifu Tap! Тапай вайфу, покупай бусты, открывай персонажей и становись лучшим! 🌸"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=share_url)],
        [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])

    await callback.message.edit_text(ref_text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "claim_daily")
async def cb_claim_daily(callback: CallbackQuery):
    tg_id = callback.from_user.id
    result = await api_post("/api/daily/claim", {"telegram_id": tg_id})

    if result.get("success"):
        text = (
            f"🎉 <b>Ты получил награду!</b>\n\n"
            f"💰 +{result['coins']} монет\n"
            f"{'⭐ +' + str(result['stars']) + ' Stars' if result['stars'] > 0 else ''}\n\n"
            f"📅 День {result['day']}/7\n\n"
            f"Возвращайся завтра за следующей наградой! 🌸"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=config.WEBAPP_URL))]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("❌ " + result.get("error", "Ошибка"), show_alert=True)

    await callback.answer()


@dp.callback_query(F.data == "already_claimed")
async def cb_already_claimed(callback: CallbackQuery):
    await callback.answer("Ты уже получил награду сегодня! Возвращайся завтра 🌸", show_alert=True)


@dp.callback_query(F.data == "confirm_clear")
async def cb_confirm_clear(callback: CallbackQuery):
    """Подтверждение очистки БД"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    result = await api_post("/api/admin/clear", {"admin_id": callback.from_user.id})
    if result.get("success"):
        await callback.message.edit_text("✅ <b>База данных полностью очищена!</b>\n\nВсе пользователи удалены.")
    else:
        await callback.message.edit_text("❌ Ошибка: " + result.get("error", "Неизвестная"))
    await callback.answer()


@dp.callback_query(F.data == "cancel_clear")
async def cb_cancel_clear(callback: CallbackQuery):
    """Отмена очистки БД"""
    await callback.message.edit_text("✅ Очистка отменена.")
    await callback.answer()


# ─── Старт бота ───

bot_instance = None

async def run_bot(block=False):
    """Запуск бота"""
    global bot_instance
    logger.info("🤖 Waifu Tap Bot запускается...")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    bot_instance = bot

    # Устанавливаем команды
    await set_commands(bot)

    # Настраиваем кнопку Menu
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎮 Waifu Tap",
                web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        )
        logger.info(f"✅ Кнопка меню установлена: {config.WEBAPP_URL}")
    except Exception as e:
        logger.warning(f"⚠️ Кнопка меню не установлена: {e}")

    logger.info("🤖 Бот запущен!")
    
    if block:
        await dp.start_polling(bot, skip_updates=True)
    else:
        # Запускаем polling в фоне
        asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    
    return bot


async def main():
    await run_bot(block=True)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
