import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import CHANNEL_URL, MAX_SCROLLS, SCROLL_PAUSE
from model import NewsPost
from news_classifier import classify_news

selenium_driver = None


def setup_selenium_driver():
    global selenium_driver

    options = Options()
    options.add_argument('--headless')
    options.set_preference(
        'general.useragent.override',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0'
    )
    selenium_driver = webdriver.Firefox(options=options)


def normalize_news_text(text: str):
    normalized_text = text.replace("@Akharinkhabar\n|\nakharinkhabar.ir", "")
    normalized_text = normalized_text.replace("@Akharinkhabar", "")
    normalized_text = normalized_text.replace("akharinkhabar.ir", "")
    normalized_text = normalized_text.replace(" | ", "")
    return normalized_text.strip()


def parse_messages(html: str, seen_sids: list[str]):
    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all(
        'div', class_=lambda x: x and x.startswith('MessageItem_messageWrapper')
    )

    for msg in messages:
        sid = msg.get('data-sid')
        if not sid or sid in seen_sids:
            continue

        text_elem = next(
            (el for el in msg.find_all('div', class_=lambda x: x and x.startswith('Text_text'))
             if not (el.parent and el.parent.get('class') and any(c.startswith('Preview_preview') for c in el.parent['class']))),
            None
        )
        text = text_elem.get_text(separator='\n', strip=True) if text_elem else ''
        normalized_text = normalize_news_text(text)

        new_post = NewsPost(sid=sid, text=normalized_text, category=classify_news(normalized_text))
        print('─' * 30 + ' NEW-POST ' + '─' * 30)
        print(f"[ {new_post.category.value if new_post.category else None} ]")
        print(new_post.text[:200])
        print(f"🆔 {new_post.sid}")

        yield new_post


def scroll_and_collect(seen_sids: list[str]):
    scroller = selenium_driver.find_element(
        By.CSS_SELECTOR, "div[class*='ChatWrapper_scrollListWrapper']"
    )

    for i in range(MAX_SCROLLS):
        soup = BeautifulSoup(selenium_driver.page_source, 'html.parser')
        top_message = soup.find(
            'div', class_=lambda x: x and x.startswith('MessageItem_messageWrapper')
        )
        top_message_sid = top_message.get('data-sid') if top_message else None
        if top_message_sid and seen_sids and top_message_sid in seen_sids:
            print(f"  ✓ به آخرین پیام قبلی رسیدیم (بعد از {i} اسکرول)")
            break

        selenium_driver.execute_script("arguments[0].scrollTop = 0;", scroller)
        time.sleep(SCROLL_PAUSE)

        if i == MAX_SCROLLS - 1:
            print(f"  ⚠ به سقف {MAX_SCROLLS} اسکرول رسیدیم")

    yield from parse_messages(selenium_driver.page_source, seen_sids)


def fetch_new_posts(seen_sids: list[str]):
    setup_selenium_driver()
    try:
        print(f"\n🔄 بررسی کانال... ({time.strftime('%H:%M:%S')})")
        selenium_driver.get(CHANNEL_URL)

        # صبر تا لود شدن اولین پیام
        WebDriverWait(selenium_driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[class*='MessageItem_messageWrapper']")
            )
        )
        time.sleep(2)  # فرصت برای رندر کامل

        yield from scroll_and_collect(seen_sids)
    finally:
        if selenium_driver:
            selenium_driver.quit()
