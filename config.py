"""
Waifu Tap — конфигурация проекта
🌸 Тыкай свою вайфу!

Все секреты (BOT_TOKEN, API_ID, API_HASH, ADMIN_ID) — в .env файле!
Скопируй .env.example → .env и заполни своими данными.
"""
import os
from dataclasses import dataclass
from typing import Optional

# Загружаем .env файл вручную (без внешних зависимостей)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                _key = _key.strip()
                _val = _val.strip().strip("\"'")
                if _key not in os.environ:
                    os.environ[_key] = _val


@dataclass
class Config:
    # ─── Telegram Bot (только из .env или переменных окружения) ───
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
    BOT_USERNAME: str = os.environ.get("BOT_USERNAME", "W3ifuTapBot")
    
    # ─── Webapp URL (для Mini App кнопки в Telegram) ───
    WEBAPP_URL: str = os.environ.get("WEBAPP_URL", "https://portfoliodesacratio.github.io/waifu-tap-temp/")
    
    # ─── API URL (для бота — на какой URL слать запросы) ───
    API_URL: str = os.environ.get("API_URL", "https://waifu-tap-bot.onrender.com")
    
    # ─── Telegram API (только из .env) ───
    TELEGRAM_API_ID: int = int(os.environ.get("TELEGRAM_API_ID", 0))
    TELEGRAM_API_HASH: str = os.environ.get("TELEGRAM_API_HASH", "")
    
    # ─── База данных ───
    DB_PATH: str = os.path.join(os.path.dirname(__file__), "data", "waifu_tap.db")
    
    # ─── Настройки игры ───
    BASE_ENERGY: int = int(os.environ.get("BASE_ENERGY", "100"))
    ENERGY_REGEN_RATE: float = float(os.environ.get("ENERGY_REGEN_RATE", "1.0"))
    ENERGY_REGEN_INTERVAL: int = int(os.environ.get("ENERGY_REGEN_INTERVAL", "3"))
    BASE_COINS_PER_TAP: float = float(os.environ.get("BASE_COINS_PER_TAP", "1.0"))
    MAX_ENERGY_BOOST: int = int(os.environ.get("MAX_ENERGY_BOOST", "500"))
    
    # ─── Настройки сервера ───
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8001"))
    
    # ─── Telegram Stars ───
    STARS_ENABLED: bool = os.environ.get("STARS_ENABLED", "true").lower() in ("1", "true", "yes")
    STARS_PRICE_MULTIPLIER: float = float(os.environ.get("STARS_PRICE_MULTIPLIER", "1.0"))
    
    # ─── Админ (только из .env) ───
    ADMIN_ID: Optional[int] = int(os.environ["ADMIN_ID"]) if os.environ.get("ADMIN_ID") else None

config = Config()
