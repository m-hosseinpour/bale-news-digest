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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        print(f"⚠ مقدار نامعتبر برای {name}={value!r}; استفاده از {default}")
        return default


IMPORTANT_CATEGORIES: list[NewsCategory] = [
    NewsCategory.WAR_CONFLICT,
    NewsCategory.POLITICS,
    NewsCategory.ECONOMY,
    NewsCategory.SCIENCE_TECH,
]

CHANNEL_SLUG = os.getenv("CHANNEL_SLUG", "akharinkhabar")

# آیدی داخلی کانال (نه آیدی Bot API) که از env خوانده می‌شود و در زمان اجرا
# هیچ‌وقت دوباره کشف نمی‌شود. اگر تنظیم نشده باشد، news_collector با خطای
# واضح فارسی کاربر را به scripts/resolve_peer_id.py هدایت می‌کند.
_RAW_PEER_ID = os.getenv("PEER_ID")
try:
    PEER_ID = int(_RAW_PEER_ID) if _RAW_PEER_ID else None
except ValueError:
    print("⚠ مقدار PEER_ID نامعتبر است؛ برای یافتنش scripts/resolve_peer_id.py را اجرا کن.")
    PEER_ID = None

MAX_PAGES_PER_RUN = _env_int("MAX_PAGES_PER_RUN", 50)
MAX_POSTS_PER_RUN = _env_int("MAX_POSTS_PER_RUN", 500)
HISTORY_PAGE_SLEEP = _env_float("HISTORY_PAGE_SLEEP", 0.3)
HTTP_TIMEOUT = _env_int("HTTP_TIMEOUT", 30)

BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")

_raw_chat_id = os.getenv("BALE_BOT_CHAT_ID")
try:
    BALE_BOT_CHAT_ID = int(_raw_chat_id) if _raw_chat_id else None
except ValueError:
    print("⚠ مقدار BALE_BOT_CHAT_ID نامعتبر است؛ None در نظر گرفته می‌شود.")
    BALE_BOT_CHAT_ID = None


# chat_id اختصاصی هر دستهٔ مهم، از env خوانده می‌شود.
# نام env: BALE_BOT_CHAT_ID_<CATEGORY> (مثلاً BALE_BOT_CHAT_ID_WAR_CONFLICT).
# اگر برای دسته‌ای تنظیم نشده باشد، آن دسته فقط در کانال اصلی ارسال می‌شود.
CATEGORY_CHAT_IDS: dict[NewsCategory, int] = {}
for _cat in IMPORTANT_CATEGORIES:
    _raw = os.getenv(f"BALE_BOT_CHAT_ID_{_cat.name}")
    if not _raw:
        continue
    try:
        CATEGORY_CHAT_IDS[_cat] = int(_raw)
    except ValueError:
        print(f"⚠ مقدار BALE_BOT_CHAT_ID_{_cat.name} نامعتبر است؛ نادیده گرفته می‌شود.")

OPEN_AI_MODEL_NAME = os.getenv("OPEN_AI_MODEL_NAME", "qwen3:4b-instruct")
OPEN_AI_BASE_URL = os.getenv("OPEN_AI_BASE_URL", "http://localhost:11434/v1")
OPEN_AI_API_KEY = os.getenv("OPEN_AI_API_KEY", "ollama")
