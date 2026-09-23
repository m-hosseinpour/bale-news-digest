import json
import re
import time
from collections.abc import Iterable

import requests

from config import (
    CHANNEL_SLUG,
    HISTORY_PAGE_SLEEP,
    HTTP_TIMEOUT,
    MAX_PAGES_PER_RUN,
    MAX_POSTS_PER_RUN,
    PEER_ID,
)
from model import NewsCategory, NewsPost
from news_classifier import classify_news

API_URL = "https://api.ble.ir/api/v1/LoadHistory"
PUBLIC_CHANNEL_URL = "https://ble.ir/s/{slug}"

# آیدی داخلی API نوع ۲ = کانال است.
PEER_TYPE_CHANNEL = 2

PEER_ID_PATTERNS = (
    re.compile(r'\\"peer\\":\{\\"type\\":(\d+),\\"id\\":(-?\d+)\}'),
    re.compile(r'"peer":\{"type":(\d+),"id":(-?\d+)\}'),
)

PEER_ID_HELP = (
    "برای پیدا کردنش این دستور را اجرا کن و مقدار چاپ‌شده را در PEER_ID داخل .env بگذار:\n"
    f"  uv run python scripts/resolve_peer_id.py {CHANNEL_SLUG}"
)


def resolve_peer_id(slug: str) -> int:
    """آیدی داخلی کانال را از صفحهٔ عمومی ble.ir/s/<slug> استخراج می‌کند."""
    url = PUBLIC_CHANNEL_URL.format(slug=slug)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"⛔ دریافت صفحهٔ کانال {slug} ناموفق بود: {e}") from e

    if response.status_code == 404:
        raise RuntimeError(f"⛔ کانال «{slug}» پیدا نشد (HTTP 404). اسلاگ را بررسی کن.")

    if response.status_code != 200:
        raise RuntimeError(
            f"⛔ صفحهٔ کانال {slug} با کد {response.status_code} برگشت؛ "
            "احتمالاً موقت است، دوباره تلاش کن."
        )

    for pattern in PEER_ID_PATTERNS:
        match = pattern.search(response.text)
        if match:
            peer_id = int(match.group(2))
            print(f"✓ آیدی داخلی کانال {slug}: {peer_id}")
            return peer_id

    raise RuntimeError(
        f"⛔ آیدی داخلی کانال {slug} در HTML صفحه پیدا نشد؛ "
        "ساختار صفحهٔ بله عوض شده است."
    )


def _validate_history(payload: object, anchor_ms: int) -> list[dict]:
    """شکل پاسخ LoadHistory را اعتبارسنجی می‌کند.

    این API مستندنشده است؛ اگر ساختارش عوض شود باید خطای واضح بدهیم، نه لیست خالی —
    وگرنه یک روز بی‌صدا هیچ خبری جمع نمی‌شود.
    """
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"⛔ پاسخ LoadHistory از نوع dict نبود ({type(payload).__name__}); "
            "قرارداد API بله عوض شده است."
        )

    history = payload.get("history")
    if not isinstance(history, list):
        raise RuntimeError(
            "⛔ کلید history در پاسخ LoadHistory نیست یا لیست نیست; "
            f"کلیدهای دریافتی: {sorted(payload)[:10]}"
        )

    if not history:
        return []

    dates: list[int] = []
    for entry in history:
        if not isinstance(entry, dict):
            raise RuntimeError(f"⛔ یکی از آیتم‌های history دیکشنری نیست: {type(entry).__name__}")

        rid = entry.get("rid")
        if not isinstance(rid, str) or not rid:
            raise RuntimeError(f"⛔ فیلد rid در آیتم history نامعتبر است: {rid!r}")

        date = entry.get("date")
        if not isinstance(date, int) or isinstance(date, bool):
            raise RuntimeError(f"⛔ فیلد date در آیتم history نامعتبر است (rid={rid}): {date!r}")

        message = entry.get("message")
        if not isinstance(message, dict):
            raise RuntimeError(
                f"⛔ فیلد message در آیتم history دیکشنری نیست (rid={rid}؛ "
                f"نوع={type(message).__name__}). قرارداد LoadHistory عوض شده است."
            )

        # message خالی در داده واقعی هم دیده می‌شود (حدود ۰٫۱٪) و یعنی «بدون محتوا»،
        # مثل emptyMessage؛ ولی دیکشنری پُر بدون هیچ شکل شناخته‌شده یعنی سرور
        # شکل‌ها را تغییر نام داده — و ادامه دادن یعنی حذف بی‌صدای همهٔ خبرها.
        if message and not any(kind in message for kind in KNOWN_MESSAGE_KINDS):
            raise RuntimeError(
                "⛔ شکل message در آیتم history ناشناخته است "
                f"(rid={rid}؛ کلیدها={sorted(message)[:10]}). "
                "قرارداد LoadHistory عوض شده است و ادامه دادن یعنی حذف بی‌صدای خبرها."
            )

        dates.append(date)

    # قفل اصلی صفحه‌بندی: اندازهٔ صفحه ثابت ۱۰ است و anchor باید هر بار عقب برود،
    # وگرنه همان ۱۰ پیام تا ابد برمی‌گردد.
    if min(dates) - 1 >= anchor_ms:
        raise RuntimeError(
            "⛔ صفحه‌بندی متوقف شد: anchor جلو نرفت "
            f"(anchor={anchor_ms}, min(date)={min(dates)}). "
            "قرارداد LoadHistory عوض شده است."
        )

    return history


def _ensure_page_progress(history: list[dict], collected_sids: set[str]) -> None:
    """صفحهٔ تازه باید حداقل یک پیام ندیده داشته باشد.

    این گارد تلهٔ اصلی را می‌گیرد: اگر منهای یک در `anchor = min(date) - 1` جا
    بیفتد، سرور همان ۱۰ پیام قبلی را برمی‌گرداند و حلقه بی‌نهایت (یا تا سقف
    صفحه) روی یک صفحه می‌ماند.
    """
    if history and all(_build_sid(entry) in collected_sids for entry in history):
        raise RuntimeError(
            "⛔ صفحه‌بندی جلو نمی‌رود: صفحهٔ دریافتی هیچ پیام جدیدی نداشت "
            f"(sid تکراری، min(date)={min(entry['date'] for entry in history)}). "
            "قرارداد صفحه‌بندی LoadHistory عوض شده است."
        )


def load_history(peer_id: int, date_ms: int) -> list[dict]:
    """یک صفحه از تاریخچه (حداکثر ۱۰ پیام) را برمی‌گرداند."""
    try:
        response = requests.post(
            API_URL,
            json={"peer": {"type": PEER_TYPE_CHANNEL, "id": peer_id}, "date": date_ms},
            headers={"Content-Type": "application/json"},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠ خطا در ارتباط با API بله: {e}")
        raise RuntimeError(f"⛔ واکشی تاریخچه از API بله ناموفق بود: {e}") from e

    try:
        payload = json.loads(response.content)
    except ValueError as e:
        print(f"⚠ پاسخ API بله JSON معتبر نبود: {e}")
        raise RuntimeError(f"⛔ پاسخ API بله JSON معتبر نبود: {e}") from e

    return _validate_history(payload, date_ms)


# سه شکل پیام که این API واقعاً برمی‌گرداند. اگر سرور شکل تازه‌ای اضافه کند
# یا یکی را تغییر نام دهد، باید خطا بدهیم: وگرنه extract_text رشتهٔ خالی
# می‌دهد، پست بی‌صدا حذف می‌شود، و تاریخچه «تمام‌شده» به نظر می‌رسد.
KNOWN_MESSAGE_KINDS = ("textMessage", "documentMessage", "emptyMessage")


def extract_text(message: dict) -> str:
    """متن پیام را از هر شکل آن بیرون می‌کشد.

    متن ویدیوها/فایل‌ها در documentMessage.caption.text است؛ در کانال‌های خبری
    این شکل غالب است و نادیده گرفتنش بخش عمدهٔ خبرها را بی‌صدا حذف می‌کند.
    """
    if not isinstance(message, dict):
        return ""

    if "textMessage" in message:
        text_message = message.get("textMessage") or {}
        if isinstance(text_message, dict):
            text = text_message.get("text")
            if isinstance(text, str):
                return text
        return ""

    if "documentMessage" in message:
        document_message = message.get("documentMessage") or {}
        if not isinstance(document_message, dict):
            return ""
        caption = document_message.get("caption") or {}
        if not isinstance(caption, dict):
            return ""
        text = caption.get("text")
        return text if isinstance(text, str) else ""

    # emptyMessage عمداً متن ندارد.
    return ""


def normalize_news_text(text: str, slug: str) -> str:
    """امضای تبلیغاتی کانال را از متن حذف می‌کند.

    در متن واقعی این خط با حرف بزرگ می‌آید («@Akharinkhabar | akharinkhabar.ir»)
    در حالی که اسلاگ کانال کوچک است، پس تطبیق باید بی‌توجه به بزرگی/کوچکی باشد.
    """
    escaped = re.escape(slug)
    promo_line = re.compile(rf"@{escaped}\s*\|\s*{escaped}\.ir", re.IGNORECASE)
    mention = re.compile(rf"@{escaped}\b", re.IGNORECASE)

    normalized = promo_line.sub("", text)
    normalized = mention.sub("", normalized)
    return normalized.strip()


def _build_sid(entry: dict) -> str:
    # rid یک رشتهٔ JSON است (ممکن است int64 منفی باشد) و باید دست‌نخورده بماند،
    # چون dedup با news_posts.json روی همین قالب انجام می‌شود.
    return f"{entry['rid']}-{entry['date']}"


def _ensure_peer_id() -> int:
    if PEER_ID is None:
        raise RuntimeError(f"⛔ مقدار PEER_ID تنظیم نشده است.\n{PEER_ID_HELP}")
    return PEER_ID


def fetch_new_posts(seen_sids: set[str]) -> Iterable[NewsPost]:
    """پست‌های جدید کانال را از API بله واکشی می‌کند و یکی‌یکی yield می‌کند."""
    peer_id = _ensure_peer_id()

    print(f"\n🔄 بررسی کانال... ({time.strftime('%H:%M:%S')})")

    anchor = int(time.time() * 1000)
    collected_sids: set[str] = set()
    new_posts = 0

    for page_index in range(MAX_PAGES_PER_RUN):
        if page_index:
            time.sleep(HISTORY_PAGE_SLEEP)

        history = load_history(peer_id, anchor)
        if not history:
            print("✓ به انتهای تاریخچهٔ کانال رسیدیم")
            return

        if page_index:
            _ensure_page_progress(history, collected_sids)

        reached_old_post = False

        for entry in history:
            # کلید یکتایی از API «rid» نیست: یک rid می‌تواند روی دو ردیف با
            # تاریخ‌های متفاوت بیاید و هر دو در news_posts.json ذخیره شده باشند.
            # پس جلوگیری از تکرار باید روی sid باشد، نه rid.
            sid = _build_sid(entry)
            if sid in seen_sids:
                print(f"  ✓ به آخرین پست قبلی رسیدیم (sid={sid})")
                reached_old_post = True
                break
            if sid in collected_sids:
                continue
            collected_sids.add(sid)

            text = normalize_news_text(extract_text(entry["message"]), CHANNEL_SLUG)
            if not text:
                continue

            category: NewsCategory | None = None
            try:
                category = classify_news(text)
            except Exception as e:
                print(f"⚠ خطا در classification برای sid={sid}: {e}")
                category = NewsCategory.UNKNOWN

            print("─" * 30 + " NEW-POST " + "─" * 30)
            print(f"[ {category.value if category else None} ]")
            print(text[:200])
            print(f"🆔 {sid}")

            new_posts += 1
            yield NewsPost(sid=sid, text=text, category=category)

            if new_posts >= MAX_POSTS_PER_RUN:
                print(f"⚠ به سقف {MAX_POSTS_PER_RUN} پست جدید رسیدیم")
                return

        if reached_old_post:
            return

        anchor = min(entry["date"] for entry in history) - 1
    else:
        print(f"⚠ به سقف {MAX_PAGES_PER_RUN} صفحه رسیدیم")


if __name__ == "__main__":
    for post in fetch_new_posts(set()):
        print(post)
