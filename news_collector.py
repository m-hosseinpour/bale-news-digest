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
        'div', class_=lambda x: x and x.startswith('MessageItem_messageWrapper__')
    )

    for msg in messages:
        sid = msg.get('data-sid')
        if not sid or sid in seen_sids:
            continue

        text_elem = next(
            (el for el in msg.find_all('div', class_=lambda x: x and x.startswith('Text_text__'))
             if not (el.parent and el.parent.get('class') and any(c.startswith('Preview_details__') for c in el.parent['class']))),
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
        By.CSS_SELECTOR, "div[class*='ChatWrapper_scrollListWrapper__']"
    )

    for i in range(MAX_SCROLLS):
        soup = BeautifulSoup(selenium_driver.page_source, 'html.parser')
        top_message = soup.find(
            'div', class_=lambda x: x and x.startswith('MessageItem_messageWrapper__')
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
                (By.CSS_SELECTOR, "div[class*='MessageItem_messageWrapper__']")
            )
        )
        time.sleep(2)  # فرصت برای رندر کامل

        yield from scroll_and_collect(seen_sids)
    finally:
        if selenium_driver:
            selenium_driver.quit()

if __name__ == '__main__':
    seen_sids = []
    html = """<div><div data-sid="3208793022177440039-1784949585855" class="MessageItem_messageWrapper__E9ZFU ChatWrapper_messageBlock__Wrs5L"><div class="BaseBubble_bubble__4oHot DefaultBubble_bubble__s_5uz Text_textMessage__nC_tz MessageItem_bubble__38sVg"><div class="Preview_preview__B_ivv" style="border-right: 3px solid rgb(242, 87, 168); --darkreader-inline-border-right: var(--darkreader-border-f257a8, #910b51);" data-darkreader-inline-border-right=""><div class="Preview_details__CVlWn"><span class="Preview_sender__HlFfO" style="color: rgb(242, 87, 168); --darkreader-inline-color: var(--darkreader-text-f257a8, #f25aaa);" data-darkreader-inline-color="">آخرین خبر</span><div class="Text_text__Um9IF TextPreview_text_preview___Mz_e"><span><strong><img style="background: url(&quot;/_next/static/media/20.41bcc406.png&quot;) 50% 41.0714% / 5700% 5700%; --darkreader-inline-bgcolor: initial;" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" "="" class="emoji" data-codepoints="1f534" alt="undefined" data-darkreader-inline-bgcolor="">آژیرهای هشدار در استان یَنبُع عربستان سعودی به صدا درآمدند</strong> @Akharinkhabar | akharinkhabar.ir</span></div></div></div><div class=""><div class="Text_text__Um9IF"><span class="p" dir="rtl"><strong><img style="background: url(&quot;/_next/static/media/20.41bcc406.png&quot;) 50% 41.0714% / 5700% 5700%; --darkreader-inline-bgcolor: initial;" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" "="" class="emoji" data-codepoints="1f534" alt="undefined" data-darkreader-inline-bgcolor="">انفجارها دوباره خمیس مشیط در عربستان را لرزاند</strong></span><span class="p" dir="ltr"><a href="https://ble.ir/Akharinkhabar" class="mention" dir="auto" data-mention="@Akharinkhabar">@Akharinkhabar</a> | <a class="link" target="_blank" href="http://akharinkhabar.ir" dir="auto">akharinkhabar.ir</a></span></div><div class="Info_info__l7qhn"><div class="Info_meta___R9G5"><div class="Info_ViewWrapper__O75PK"><svg width="13" height="13" viewBox="0 0 13 13" fill="none" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M8.21353 6.52916C8.21353 7.47491 7.44653 8.24136 6.50078 8.24136C5.55503 8.24136 4.78857 7.47491 4.78857 6.52916C4.78857 5.58286 5.55503 4.81641 6.50078 4.81641C7.44653 4.81641 8.21353 5.58286 8.21353 6.52916Z" stroke="#7A869A" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" data-darkreader-inline-stroke="" style="--darkreader-inline-stroke: var(--darkreader-text-7a869a, #9e9689);"></path><path fill-rule="evenodd" clip-rule="evenodd" d="M6.49908 10.4837C8.56175 10.4837 10.4484 9.00066 11.5106 6.52849C10.4484 4.05633 8.56175 2.57324 6.49908 2.57324H6.50125C4.43858 2.57324 2.55195 4.05633 1.48975 6.52849C2.55195 9.00066 4.43858 10.4837 6.50125 10.4837H6.49908Z" stroke="#7A869A" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" data-darkreader-inline-stroke="" style="--darkreader-inline-stroke: var(--darkreader-text-7a869a, #9e9689);"></path></svg><p class="Info_Text__LVysg">۱۵۱.۱K</p></div><p class="Info_date__fCTQ4">۶:۴۹</p></div></div></div></div></div><div>"""
    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all(
        'div', class_=lambda x: x and x.startswith('MessageItem_messageWrapper__')
    )

    for msg in messages:
        sid = msg.get('data-sid')
        if not sid or sid in seen_sids:
            continue

        text_elem = next(
            (el for el in msg.find_all('div', class_=lambda x: x and x.startswith('Text_text__'))
             if not (el.parent and el.parent.get('class') and any(c.startswith('Preview_details__') for c in el.parent['class']))),
            None
        )
        text = text_elem.get_text(separator='\n', strip=True) if text_elem else ''
        normalized_text = normalize_news_text(text)

        new_post = NewsPost(sid=sid, text=normalized_text, category=None)
        print('─' * 30 + ' NEW-POST ' + '─' * 30)
        print(f"[ {new_post.category.value if new_post.category else None} ]")
        print(new_post.text[:200])
        print(f"🆔 {new_post.sid}")
