import time
from collections.abc import Iterable

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import (
    CHANNEL_URL,
    MAX_SCROLLS,
    SCROLL_PAUSE,
    HEADLESS,
    PAGE_LOAD_TIMEOUT,
    WEBDRIVER_WAIT_TIMEOUT,
    MAX_DRIVER_REUSE,
    DISABLE_IMAGES,
)
from model import NewsCategory, NewsPost
from news_classifier import classify_news


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
    "Gecko/20100101 Firefox/127.0"
)

MESSAGE_SELECTOR = "div[class*='MessageItem_messageWrapper__']"
SCROLL_SELECTOR = "div[class*='ChatWrapper_scrollListWrapper__']"
TEXT_SELECTOR = "div[class*='Text_text__']"


def normalize_news_text(text: str) -> str:
    normalized_text = text.replace("@Akharinkhabar\n|\nakharinkhabar.ir", "")
    normalized_text = normalized_text.replace("@Akharinkhabar", "")
    normalized_text = normalized_text.replace("akharinkhabar.ir", "")
    normalized_text = normalized_text.replace(" | ", "")
    return normalized_text.strip()


class NewsCollector:
    """
    مدیریت چرخه‌عمر Firefox برای اجرای مداوم.

    مزیت نسبت به نسخهٔ قبلی:
    - Firefox برای هر fetch از صفر ساخته نمی‌شود.
    - بعد از collect، صفحه به about:blank می‌رود تا RAM آزاد شود.
    - بعد از تعداد مشخصی fetch، Firefox restart می‌شود.
    - در صورت خطا، session خراب بسته می‌شود و دفعهٔ بعد session جدید ساخته می‌شود.
    """

    def __init__(self) -> None:
        self.driver: webdriver.Firefox | None = None
        self.fetch_count = 0

    def __enter__(self) -> "NewsCollector":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self.driver is None:
            self.driver = self._create_driver()

    def stop(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except WebDriverException as e:
                print(f"⚠ خطا در بستن Firefox: {e}")
            finally:
                self.driver = None
                self.fetch_count = 0

    def restart(self) -> None:
        print("♻️ راه‌اندازی مجدد Firefox برای جلوگیری از نشتی حافظه...")
        self.stop()
        self.start()

    def _create_driver(self) -> webdriver.Firefox:
        options = Options()

        if HEADLESS:
            options.add_argument("--headless")

        options.page_load_strategy = "normal"

        options.set_preference("general.useragent.override", USER_AGENT)

        # غیرفعال کردن تصویرها معمولاً سرعت لود و مصرف منابع را بهتر می‌کند.
        if DISABLE_IMAGES:
            options.set_preference("permissions.default.image", 2)

        # چند preference برای سبک‌تر شدن Firefox
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("media.autoplay.default", 5)
        options.set_preference("reader.parse-on-load.enabled", False)

        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.set_window_size(1366, 900)

        return driver

    def _get_top_sid(self, driver: webdriver.Firefox) -> str | None:
        try:
            element = driver.find_element(By.CSS_SELECTOR, MESSAGE_SELECTOR)
            return element.get_attribute("data-sid")
        except NoSuchElementException:
            return None

    def _wait_for_top_sid_change(
            self,
            driver: webdriver.Firefox,
            old_sid: str | None,
            timeout: int,
    ) -> bool:
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: self._get_top_sid(d) != old_sid
            )
            return True
        except TimeoutException:
            return False

    def _scroll_to_previous_messages(
            self,
            driver: webdriver.Firefox,
            seen_sids: set[str],
    ) -> None:
        if MAX_SCROLLS <= 0:
            return

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SCROLL_SELECTOR))
        )

        last_top_sid = None
        stable_rounds = 0

        for i in range(MAX_SCROLLS):
            top_sid = self._get_top_sid(driver)

            if top_sid and seen_sids and top_sid in seen_sids:
                print(f"  ✓ به آخرین پیام قبلی رسیدیم (بعد از {i} اسکرول)")
                break

            # اگر چند بار پشت سر هم top_sid عوض نشد، یعنی اسکرول باعث لود پیام قدیمی‌تر نشده است.
            # چون کانال خیلی قدیمی است و عملاً هیچ‌وقت به ابتدای کانال نمی‌رسیم،
            # این وضعیت معمولاً نشانهٔ کندی سرور بله یا مشکل شبکه است.
            if top_sid == last_top_sid:
                stable_rounds += 1
                if stable_rounds >= 3:
                    raise RuntimeError(
                        "اسکرول به بالا متوقف شده است؛ top_sid چند بار تغییر نکرد. "
                        "احتمالاً سرور بله یا شبکه کند است و پیام‌های قدیمی‌تر لود نمی‌شوند. "
                        f"scroll_index={i}, last_top_sid={last_top_sid}"
                    )
            else:
                stable_rounds = 0

            last_top_sid = top_sid

            try:
                scroller = driver.find_element(By.CSS_SELECTOR, SCROLL_SELECTOR)
                driver.execute_script("arguments[0].scrollTop = 0;", scroller)
            except WebDriverException:
                # اگر عنصر stale شد یا خطایی پیش آمد، دوباره پیدا می‌کنیم.
                scroller = WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SCROLL_SELECTOR))
                )
                driver.execute_script("arguments[0].scrollTop = 0;", scroller)

            # به‌جای sleep خشک، صبر می‌کنیم تا top_sid عوض شود؛
            # اگر نشد، timeout می‌خورد و ادامه می‌دهیم.
            changed = self._wait_for_top_sid_change(
                driver,
                top_sid,
                SCROLL_PAUSE + 3,
                )

            if not changed:
                time.sleep(0.3)
        else:
            print(f"  ⚠ به سقف {MAX_SCROLLS} اسکرول رسیدیم")

    def _extract_raw_posts(
            self,
            html: str,
            seen_sids: set[str],
    ) -> list[NewsPost]:
        soup = BeautifulSoup(html, "html.parser")
        raw_posts: list[NewsPost] = []
        local_seen: set[str] = set()

        messages = soup.find_all(
            "div",
            class_=lambda x: x and x.startswith("MessageItem_messageWrapper__"),
        )

        for msg in messages:
            sid = msg.get("data-sid")

            if not sid or sid in seen_sids or sid in local_seen:
                continue

            text_elem = next(
                (
                    el
                    for el in msg.find_all(
                    "div",
                    class_=lambda x: x and x.startswith("Text_text__"),
                )
                    if not (
                        el.parent
                        and el.parent.get("class")
                        and any(
                    c.startswith("Preview_details__")
                    for c in el.parent["class"]
                )
                )
                ),
                None,
            )

            text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""
            normalized_text = normalize_news_text(text)

            if not normalized_text:
                continue

            local_seen.add(sid)
            raw_posts.append(
                NewsPost(
                    sid=sid,
                    text=normalized_text,
                    category=None,
                )
            )

        return raw_posts

    def fetch_new_posts(self, seen_sids: set[str]) -> Iterable[NewsPost]:
        self.start()

        driver = self.driver
        if driver is None:
            raise RuntimeError("Firefox driver initialized نشد.")

        try:
            print(f"\n🔄 بررسی کانال... ({time.strftime('%H:%M:%S')})")

            driver.get(CHANNEL_URL)

            WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, MESSAGE_SELECTOR))
            )

            # یک مکث کوتاه برای رندر اولیه؛
            # اگر لازم بود، می‌توانی این را 2 هم نگه داری.
            time.sleep(1)

            self._scroll_to_previous_messages(driver, seen_sids)

            # DOM نهایی را می‌گیریم.
            html = driver.page_source

            # آزاد کردن صفحه قبل از classification / LLM.
            # این کار باعث می‌شود RAM مربوط به صفحهٔ کانال کمتر نگه داشته شود.
            try:
                driver.get("about:blank")
            except WebDriverException:
                # اگر مرورگر دیگر سالم نیست، آن را ببند؛ دفعهٔ بعد دوباره ساخته می‌شود.
                self.stop()

            self.fetch_count += 1

            raw_posts = self._extract_raw_posts(html, seen_sids)
            print(f"📦 {len(raw_posts)} پست جدید پیدا شد")

            # restart دوره‌ای برای جلوگیری از memory leak
            if MAX_DRIVER_REUSE > 0 and self.fetch_count >= MAX_DRIVER_REUSE:
                self.restart()

            # classification بعد از جمع‌آوری DOM انجام می‌شود،
            # نه همزمان با اسکرول‌های سنگین.
            for post in raw_posts:
                category: NewsCategory | None = None

                if post.text:
                    try:
                        category = classify_news(post.text)
                    except Exception as e:
                        print(f"⚠ خطا در classification برای sid={post.sid}: {e}")
                        category = NewsCategory.UNKNOWN

                print("─" * 30 + " NEW-POST " + "─" * 30)
                print(f"[ {category.value if category else None} ]")
                print(post.text[:200])
                print(f"🆔 {post.sid}")

                yield NewsPost(
                    sid=post.sid,
                    text=post.text,
                    category=category,
                )

        except Exception:
            # اگر خطای جدی پیش آمد، session خراب را می‌بندیم
            # تا در چرخهٔ بعد یک Firefox سالم ساخته شود.
            self.stop()
            raise


# برای سازگاری با کدهای قدیمی یا استفادهٔ یک‌باره.
# اگر فقط یک‌بار صدا زده شود، Firefox باز و در انتها بسته می‌شود.
def fetch_new_posts(seen_sids: set[str]) -> Iterable[NewsPost]:
    with NewsCollector() as collector:
        yield from collector.fetch_new_posts(seen_sids)


if __name__ == "__main__":
    seen: set[str] = set()

    with NewsCollector() as collector:
        for post in collector.fetch_new_posts(seen):
            print(post)
