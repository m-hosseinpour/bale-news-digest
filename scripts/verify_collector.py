"""اعتبارسنجی جمع‌آوری از API بله.

    uv run python scripts/verify_collector.py [تعداد_پست]

تعداد پیام‌های آخر کانال را به تفکیک نوع می‌شمارد، نشان می‌دهد چند تایشان بعد از
استخراج متن غیرخالی دارند، و نرخ تطبیق sid با news_posts.json را گزارش می‌کند.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import CHANNEL_SLUG, PEER_ID  # noqa: E402
from news_collector import _build_sid, extract_text, load_history, normalize_news_text  # noqa: E402
from utils import POSTS_FILE  # noqa: E402

DEFAULT_SAMPLE = 100
PAGE_SLEEP = 0.3


def _message_kind(message: dict) -> str:
    for kind in ("textMessage", "documentMessage", "emptyMessage"):
        if kind in message:
            return kind
    return "unknown"


def _fetch_sample(peer_id: int, sample_size: int) -> list[dict]:
    anchor = int(time.time() * 1000)
    entries: list[dict] = []
    seen_rids: set[str] = set()

    while len(entries) < sample_size:
        history = load_history(peer_id, anchor)
        if not history:
            print("✓ به انتهای تاریخچه رسیدیم")
            break

        for entry in history:
            if entry["rid"] in seen_rids:
                continue
            seen_rids.add(entry["rid"])
            entries.append(entry)

        anchor = min(entry["date"] for entry in history) - 1
        time.sleep(PAGE_SLEEP)

    return entries[:sample_size]


def main() -> int:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE

    if PEER_ID is None:
        print("⛔ مقدار PEER_ID تنظیم نشده است.")
        print(f"  uv run python scripts/resolve_peer_id.py {CHANNEL_SLUG}")
        return 1

    print(f"کانال: {CHANNEL_SLUG} · PEER_ID: {PEER_ID} · نمونه: {sample_size} پیام\n")

    entries = _fetch_sample(PEER_ID, sample_size)
    if not entries:
        print("⛔ هیچ پیامی واکشی نشد.")
        return 1

    kinds: Counter[str] = Counter()
    with_document_caption = 0
    non_empty_text = 0
    texts_by_sid: dict[str, str] = {}

    for entry in entries:
        message = entry["message"]
        kind = _message_kind(message)
        kinds[kind] += 1

        raw = extract_text(message)
        if kind == "documentMessage" and raw.strip():
            with_document_caption += 1

        text = normalize_news_text(raw, CHANNEL_SLUG)
        if text:
            non_empty_text += 1
            texts_by_sid[_build_sid(entry)] = text

    existing_sids: set[str] = set()
    if POSTS_FILE.exists():
        stored = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
        existing_sids = {post["sid"] for post in stored}
    else:
        print(f"⚠ فایل {POSTS_FILE.name} وجود ندارد؛ نرخ تطبیق محاسبه نمی‌شود.")

    print("── شمارش به تفکیک نوع پیام ──")
    for kind, count in kinds.most_common():
        share = count / len(entries) * 100
        print(f"  {kind:<18} {count:>4}  ({share:.0f}%)")

    print("\n── استخراج متن ──")
    print(f"  documentMessage با caption غیرخالی: {with_document_caption} از {kinds['documentMessage']}")
    print(f"  متن غیرخالی بعد از normalize:        {non_empty_text} از {len(entries)}")

    print("\n── سازگاری dedup ──")
    if existing_sids:
        fetched_sids = set(texts_by_sid)
        matched = fetched_sids & existing_sids
        rate = len(matched) / len(fetched_sids) * 100 if fetched_sids else 0.0
        print(f"  sid های موجود در {POSTS_FILE.name}: {len(existing_sids)}")
        print(f"  sid های واکشی‌شده:                   {len(fetched_sids)}")
        print(f"  تطبیق:                              {len(matched)}  ({rate:.0f}%)")
    else:
        print("  (داده‌ای برای مقایسه نیست)")

    if with_document_caption == 0 and kinds["documentMessage"] > 0:
        print("\n⛔ هشدار: هیچ متنی از documentMessage بیرون نیامد — caption از دست رفته است.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
