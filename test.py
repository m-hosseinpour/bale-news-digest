from config import SUMMARIZE_BATCH, OPEN_AI_MODEL_NAME
from main import IMPORTANT_CATEGORIES
from model import NewsPost
from news_classifier import classify_news
from news_summarizer import summarize_and_post_links
from utils import load_posts

if __name__ == '__main__':
    print('+' * 40)
    print(f'Using model: {OPEN_AI_MODEL_NAME}')
    print('+' * 40)
    all_posts: list[NewsPost] = load_posts()

    important_batch = []
    for post in all_posts:
        new_post = NewsPost(sid=post.sid, text=post.text, category=post.category)
        print('─' * 30 + ' POST ' + '─' * 30)
        print(f"[ {new_post.category.value if new_post.category else None} ]")
        if (post.category != new_post.category):
            print(f"=========================> old category: {post.category.value if post.category else None}")
        print(new_post.text)
        print(f"🆔 {new_post.sid}")

        if new_post.category and new_post.category in IMPORTANT_CATEGORIES:
            important_batch.append(new_post)

        if len(important_batch) >= SUMMARIZE_BATCH:
            summarize_and_post_links(important_batch)
            important_batch = []

    if important_batch:
        summarize_and_post_links(important_batch)
