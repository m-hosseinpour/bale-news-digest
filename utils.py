import json
from pathlib import Path

from pydantic import TypeAdapter

from model import NewsPost


BASE_DIR = Path(__file__).resolve().parent
POSTS_FILE = BASE_DIR / "news_posts.json"

NewsPostList = TypeAdapter(list[NewsPost])


def load_posts() -> list[NewsPost]:
    if POSTS_FILE.exists():
        try:
            return NewsPostList.validate_json(POSTS_FILE.read_bytes())
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠ خطا در خواندن فایل: {e} — با لیست خالی شروع می‌شود")

    return []


def save_posts(news_posts: list[NewsPost]) -> None:
    try:
        data: bytes = NewsPostList.dump_json(news_posts, indent=2)
        POSTS_FILE.write_bytes(data)
    except IOError as e:
        print(f"⚠ خطا در نوشتن فایل: {e}")
