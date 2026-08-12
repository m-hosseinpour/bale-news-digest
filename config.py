import os

from dotenv import load_dotenv

from model import NewsCategory

load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        print(f"⚠ مقدار نامعتبر برای {name}={value!r}; استفاده از {default}")
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


IMPORTANT_CATEGORIES: list[NewsCategory] = [
    NewsCategory.WAR_CONFLICT,
    NewsCategory.POLITICS,
    NewsCategory.ECONOMY,
    NewsCategory.SCIENCE_TECH,
    NewsCategory.UNKNOWN,
]

CHANNEL_URL = os.getenv("CHANNEL_URL", "https://ble.ir/s/akharinkhabar")

MAX_SCROLLS = _env_int("MAX_SCROLLS", 500)
SCROLL_PAUSE = _env_int("SCROLL_PAUSE", 2)

BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")

_raw_chat_id = os.getenv("BALE_BOT_CHAT_ID")
try:
    BALE_BOT_CHAT_ID = int(_raw_chat_id) if _raw_chat_id else None
except ValueError:
    print("⚠ مقدار BALE_BOT_CHAT_ID نامعتبر است؛ None در نظر گرفته می‌شود.")
    BALE_BOT_CHAT_ID = None

SUMMARIZE_BATCH = _env_int("SUMMARIZE_BATCH", 3)

OPEN_AI_MODEL_NAME = os.getenv("OPEN_AI_MODEL_NAME", "qwen3:4b-instruct")
OPEN_AI_BASE_URL = os.getenv("OPEN_AI_BASE_URL", "http://localhost:11434/v1")
OPEN_AI_API_KEY = os.getenv("OPEN_AI_API_KEY", "ollama")

# تنظیمات Selenium / Firefox
HEADLESS = _env_bool("HEADLESS", True)
DISABLE_IMAGES = _env_bool("DISABLE_IMAGES", True)
PAGE_LOAD_TIMEOUT = _env_int("PAGE_LOAD_TIMEOUT", 45)
WEBDRIVER_WAIT_TIMEOUT = _env_int("WEBDRIVER_WAIT_TIMEOUT", 20)

# بعد از این تعداد fetch، Firefox restart می‌شود.
# برای جلوگیری از memory leak روی VPS مفید است.
# اگر 0 باشد restart خودکار غیرفعال می‌شود.
MAX_DRIVER_REUSE = _env_int("MAX_DRIVER_REUSE", 20)
