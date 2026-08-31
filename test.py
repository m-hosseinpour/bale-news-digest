from config import OPEN_AI_MODEL_NAME
from main import IMPORTANT_CATEGORIES
from model import NewsPost
from news_classifier import classify_news
from news_summarizer import compose_message, summarize_single_post
from utils import load_posts

if __name__ == '__main__':
    print('+' * 40)
    print(f'Using model: {OPEN_AI_MODEL_NAME}')
    print('+' * 40)
    all_posts: list[NewsPost] = load_posts()

    for post in all_posts:
        new_post = NewsPost(sid=post.sid, text=post.text, category=classify_news(post.text))
        print('─' * 30 + ' POST ' + '─' * 30)
        print(f"[ {new_post.category.value if new_post.category else None} ]")
        if (post.category != new_post.category):
            print(f"=========================> old category: {post.category.value if post.category else None}")
        print(new_post.text)
        print(f"🆔 {new_post.sid}")

        if new_post.category and new_post.category in IMPORTANT_CATEGORIES:
            summary = summarize_single_post(new_post)
            print('=' * 30 + ' MESSAGE-TO-SEND ' + '=' * 30)
            print(compose_message(new_post, summary))
