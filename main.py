from bale_bot_message_sender import send_message
from config import (
    BALE_BOT_CHAT_ID,
    CATEGORY_CHAT_IDS,
    IMPORTANT_CATEGORIES,
    SUMMARIZE_BATCH,
)
from model import NewsCategory, NewsPost
from news_collector import NewsCollector
from news_summarizer import summarize_and_post_links
from utils import load_posts, save_posts


def send_summary_batch(batch: list[NewsPost]) -> list[NewsPost]:
    if not batch:
        return []

    summary = summarize_and_post_links(batch)

    # کانال اصلی: همیشه (اگر تنظیم شده باشد)
    if BALE_BOT_CHAT_ID is not None:
        send_message(summary, BALE_BOT_CHAT_ID)

    # کانال‌های اختصاصی هر دسته: خلاصهٔ فیلترشده برای همان دسته
    for category, chat_id in CATEGORY_CHAT_IDS.items():
        category_posts = [p for p in batch if p.category == category]
        if not category_posts:
            continue
        category_summary = summarize_and_post_links(category_posts)
        send_message(category_summary, chat_id)

    return []


def run_once() -> None:
    all_posts: list[NewsPost] = load_posts()
    seen_sids: set[str] = {p.sid for p in all_posts}
    important_batch: list[NewsPost] = []

    with NewsCollector() as collector:
        for new_post in collector.fetch_new_posts(seen_sids):
            all_posts.append(new_post)
            seen_sids.add(new_post.sid)

            if new_post.category and new_post.category in IMPORTANT_CATEGORIES:
                important_batch.append(new_post)

            if SUMMARIZE_BATCH > 0 and len(important_batch) >= SUMMARIZE_BATCH:
                important_batch = send_summary_batch(important_batch)

                all_posts = all_posts[-1000:]
                save_posts(all_posts)

        if important_batch:
            send_summary_batch(important_batch)

        all_posts = all_posts[-1000:]
        save_posts(all_posts)


if __name__ == "__main__":
    run_once()
