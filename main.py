from bale_bot_message_sender import send_message
from config import SUMMARIZE_BATCH, IMPORTANT_CATEGORIES
from model import NewsPost
from news_collector import NewsCollector
from news_summarizer import summarize_and_post_links
from utils import load_posts, save_posts


def send_summary_batch(batch: list[NewsPost]) -> list[NewsPost]:
    if not batch:
        return []

    summary = summarize_and_post_links(batch)
    send_message(summary)
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
