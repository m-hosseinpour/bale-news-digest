from bale_bot_message_sender import send_post
from config import (
    BALE_BOT_CHAT_ID,
    CATEGORY_CHAT_IDS,
    IMPORTANT_CATEGORIES,
    MAX_STORED_POSTS,
    MIN_IMPORTANCE,
)
from model import IMPORTANCE_RANK, NewsPost
from news_collector import fetch_new_posts
from news_summarizer import compose_message, summarize_single_post
from utils import load_posts, save_posts


def _targets_for_post(post: NewsPost) -> list[int]:
    """Return all chat ids that should receive this important post.

    The main channel (if configured) is always included. The post's category's
    dedicated channel (if configured) is appended.
    """
    targets: list[int] = []
    if BALE_BOT_CHAT_ID is not None:
        targets.append(BALE_BOT_CHAT_ID)
    if post.category and post.category in CATEGORY_CHAT_IDS:
        targets.append(CATEGORY_CHAT_IDS[post.category])
    return targets


def _meets_importance(post: NewsPost) -> bool:
    """آیا اهمیت پست به آستانهٔ ارسال می‌رسد؟

    پستی که اهمیتش سنجیده نشده (None) فرستاده می‌شود؛ خرابیِ سنجش نباید خبر را
    بی‌صدا حذف کند.
    """
    if post.importance is None:
        return True
    return IMPORTANCE_RANK[post.importance] >= IMPORTANCE_RANK[MIN_IMPORTANCE]


def dispatch_post(post: NewsPost) -> None:
    summary = summarize_single_post(post)
    message = compose_message(post, summary)

    print('=' * 50 + ' MESSAGE-TO-SEND ' + '=' * 50)
    print(message)

    for chat_id in _targets_for_post(post):
        send_post(message, post.media_url, post.media_kind, chat_id)


def run_once() -> None:
    all_posts: list[NewsPost] = load_posts()
    seen_sids: set[str] = {p.sid for p in all_posts}

    for new_post in fetch_new_posts(seen_sids):
        all_posts.append(new_post)
        seen_sids.add(new_post.sid)

        if (
            new_post.category
            and new_post.category in IMPORTANT_CATEGORIES
            and _meets_importance(new_post)
        ):
            dispatch_post(new_post)

        all_posts = all_posts[-MAX_STORED_POSTS:]
        save_posts(all_posts)


if __name__ == "__main__":
    run_once()
