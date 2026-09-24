import os

from dotenv import load_dotenv

from model import Importance, NewsCategory

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


def _env_importance(name: str, default: Importance) -> Importance:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return Importance(value.strip().lower())
    except ValueError:
        print(f"⚠ مقدار نامعتبر برای {name}={value!r}; استفاده از {default.value}")
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

# کمترین سطح اهمیت برای ارسال به کانال: major | normal | trivial.
# پیش‌فرض MAJOR است تا کانال فقط رویدادهای مشخص را بگیرد (هدف: چند ده پیام
# در روز به‌جای ~۹۰). پستی که اهمیتش سنجیده نشده (None) همیشه فرستاده می‌شود.
MIN_IMPORTANCE = _env_importance("MIN_IMPORTANCE", Importance.MAJOR)

CHANNEL_SLUG = os.getenv("CHANNEL_SLUG", "akharinkhabar")

_INT32_MAX = 2**31 - 1


def _parse_peer_id(raw: str | None) -> int | None:
    """PEER_ID را از رشتهٔ env می‌سازد؛ None یعنی تنظیم‌نشده یا نامعتبر.

    API بله آیدی را در int32 می‌خواهد و مقدار بیرون بازه را با خطای مبهم Go رد
    می‌کند؛ پس همین‌جا می‌گیریم تا پیام واضح بدهیم.
    """
    if not raw:
        return None

    try:
        peer_id = int(raw)
    except ValueError:
        print("⚠ مقدار PEER_ID نامعتبر است؛ برای یافتنش scripts/resolve_peer_id.py را اجرا کن.")
        return None

    if not -_INT32_MAX - 1 <= peer_id <= _INT32_MAX:
        print(f"⚠ مقدار PEER_ID={peer_id} بیرون بازهٔ int32 است؛ برای یافتنش scripts/resolve_peer_id.py را اجرا کن.")
        return None

    return peer_id


# آیدی داخلی کانال (نه آیدی Bot API) که از env خوانده می‌شود و در زمان اجرا
# هیچ‌وقت دوباره کشف نمی‌شود. اگر تنظیم نشده باشد، news_collector با خطای
# واضح فارسی کاربر را به scripts/resolve_peer_id.py هدایت می‌کند.
PEER_ID = _parse_peer_id(os.getenv("PEER_ID"))

MAX_PAGES_PER_RUN = _env_int("MAX_PAGES_PER_RUN", 50)
MAX_POSTS_PER_RUN = _env_int("MAX_POSTS_PER_RUN", 500)
# سقف نگهداری تاریخچهٔ دیده‌شده در news_posts.json. هم برای جلوگیری از ارسال
# دوباره و هم برای بررسی/تست روی داده واقعی نگه داشته می‌شود؛ ۵۰۰۰ پست حدود
# ۳ مگابایت است.
MAX_STORED_POSTS = _env_int("MAX_STORED_POSTS", 5000)
HISTORY_PAGE_SLEEP = _env_float("HISTORY_PAGE_SLEEP", 0.3)
HTTP_TIMEOUT = _env_int("HTTP_TIMEOUT", 30)

BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")

_raw_chat_id = os.getenv("BALE_BOT_CHAT_ID")
try:
    BALE_BOT_CHAT_ID = int(_raw_chat_id) if _raw_chat_id else None
except ValueError:
    print("⚠ مقدار BALE_BOT_CHAT_ID نامعتبر است؛ None در نظر گرفته می‌شود.")
    BALE_BOT_CHAT_ID = None

OPEN_AI_MODEL_NAME = os.getenv("OPEN_AI_MODEL_NAME", "qwen3:4b-instruct")
OPEN_AI_BASE_URL = os.getenv("OPEN_AI_BASE_URL", "http://localhost:11434/v1")
OPEN_AI_API_KEY = os.getenv("OPEN_AI_API_KEY", "ollama")
