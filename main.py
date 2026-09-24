from bale_bot_message_sender import send_post
from config import BALE_BOT_CHAT_ID, MAX_STORED_POSTS, MIN_IMPORTANCE
from model import IMPORTANCE_RANK, NewsPost
from news_collector import fetch_new_posts
from news_summarizer import compose_message, summarize_single_post
from utils import load_posts, save_posts


def _meets_importance(post: NewsPost) -> bool:
    """آیا اهمیت پست به آستانهٔ ارسال می‌رسد؟

    پستی که اهمیتش سنجیده نشده (None) فرستاده می‌شود؛ خرابیِ سنجش نباید خبر را
    بی‌صدا حذف کند.
    """
    if post.importance is None:
        return True
    return IMPORTANCE_RANK[post.importance] >= IMPORTANCE_RANK[MIN_IMPORTANCE]


def dispatch_post(post: NewsPost) -> None:
    """خلاصه را فقط به کانال اصلی می‌فرستد؛ کانال اختصاصی دسته‌ها وجود ندارد."""
    if BALE_BOT_CHAT_ID is None:
        print("⚠ BALE_BOT_CHAT_ID تنظیم نشده؛ پست ارسال نشد.")
        return

    summary = summarize_single_post(post)
    message = compose_message(post, summary)

    print('=' * 50 + ' MESSAGE-TO-SEND ' + '=' * 50)
    print(message)

    send_post(message, post.media_url, post.media_kind, BALE_BOT_CHAT_ID)


def run_once() -> None:
    all_posts: list[NewsPost] = load_posts()
    seen_sids: set[str] = {p.sid for p in all_posts}

    for new_post in fetch_new_posts(seen_sids):
        all_posts.append(new_post)
        seen_sids.add(new_post.sid)

        if _meets_importance(new_post):
            dispatch_post(new_post)

        all_posts = all_posts[-MAX_STORED_POSTS:]
        save_posts(all_posts)


if __name__ == "__main__":
    run_once()
