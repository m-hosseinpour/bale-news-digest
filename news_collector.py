import time
from collections.abc import Iterable

from bs4 import BeautifulSoup
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import (
    CHANNEL_URL,
    MAX_SCROLLS,
    SCROLL_PAUSE,
    HEADLESS,
    PAGE_LOAD_TIMEOUT,
    WEBDRIVER_WAIT_TIMEOUT,
    MAX_DRIVER_REUSE,
    DISABLE_IMAGES,
    CHROMIUM_EXECUTABLE_PATH,
)
from model import NewsCategory, NewsPost
from news_classifier import classify_news


# UA پیش‌فرض headless شامل «HeadlessChrome» است که سیگنال بات محسوب می‌شود؛
# پس عمداً یک UA معمولی کروم ست می‌کنیم.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
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


def _abort_images(route: Route) -> None:
    if route.request.resource_type == "image":
        route.abort()
    else:
        route.continue_()


class NewsCollector:
    """
    مدیریت چرخه‌عمر Chromium (Playwright) برای اجرای مداوم.

    مزیت‌ها نسبت به نسخهٔ Selenium:
    - locatorها خودشان auto-wait و re-resolve می‌کنند؛ دیگر نیازی به
      مدیریت دستی stale element و WebDriverWait نیست.
    - هر fetch یک context تازه می‌سازد و در پایان می‌بندد؛ هم state ایزوله
      می‌شود و هم حافظهٔ صفحه کاملاً آزاد می‌شود (جانشین about:blank).
    - بعد از تعداد مشخصی fetch، فقط مرورگر restart می‌شود، نه کل رانتایم
      Playwright؛ پس restart ارزان‌تر است.
    - در صورت خطا، session خراب بسته می‌شود و دفعهٔ بعد session جدید ساخته می‌شود.
    """

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.fetch_count = 0

    def __enter__(self) -> "NewsCollector":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self.browser is not None:
            return

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        self.browser = self._launch_browser()

    def stop(self) -> None:
        self._close_browser()

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as e:
                print(f"⚠ خطا در بستن Playwright: {e}")
            finally:
                self._playwright = None

        self.fetch_count = 0

    def restart(self) -> None:
        print("♻️ راه‌اندازی مجدد Chromium برای جلوگیری از نشتی حافظه...")
        self._close_browser()
        self.browser = self._launch_browser()
        self.fetch_count = 0

    def _close_browser(self) -> None:
        if self.browser is None:
            return

        try:
            self.browser.close()
        except Exception as e:
            print(f"⚠ خطا در بستن Chromium: {e}")
        finally:
            self.browser = None

    def _launch_browser(self) -> Browser:
        if self._playwright is None:
            raise RuntimeError("Playwright runtime initialized نشد.")

        options: dict = {
            "headless": HEADLESS,
            # /dev/shm روی VPSهای کوچک معمولاً کم است و باعث crash می‌شود.
            "args": ["--disable-dev-shm-usage"],
        }

        # در محیط‌هایی که دانلود مرورگر Playwright بلاک است، یک Chromium محلی
        # (ساخته‌شده با install_chromium.py) استفاده می‌شود.
        if CHROMIUM_EXECUTABLE_PATH:
            options["executable_path"] = CHROMIUM_EXECUTABLE_PATH

        return self._playwright.chromium.launch(**options)

    def _open_page(self) -> tuple[BrowserContext, Page]:
        browser = self.browser
        if browser is None:
            raise RuntimeError("Chromium browser initialized نشد.")

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
        )

        if DISABLE_IMAGES:
            context.route("**/*", _abort_images)

        page = context.new_page()
        page.set_default_timeout(WEBDRIVER_WAIT_TIMEOUT * 1000)
        page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT * 1000)

        return context, page

    def _get_top_sid(self, page: Page) -> str | None:
        # معادل بدون‌انتظارِ find_element + get_attribute؛ چون count/evaluate
        # خودشان re-resolve می‌کنند، مشکل stale element منتفی است.
        return page.evaluate(
            """(selector) => {
                const el = document.querySelector(selector);
                return el ? el.getAttribute("data-sid") : null;
            }""",
            MESSAGE_SELECTOR,
        )

    def _wait_for_top_sid_change(
            self,
            page: Page,
            old_sid: str | None,
            timeout: int,
    ) -> bool:
        try:
            page.wait_for_function(
                """(args) => {
                    const el = document.querySelector(args.selector);
                    return el !== null && el.getAttribute("data-sid") !== args.old;
                }""",
                arg={"selector": MESSAGE_SELECTOR, "old": old_sid},
                timeout=timeout * 1000,
            )
            return True
        except PlaywrightTimeoutError:
            return False

    def _scroll_to_previous_messages(
            self,
            page: Page,
            seen_sids: set[str],
    ) -> None:
        if MAX_SCROLLS <= 0:
            return

        page.locator(SCROLL_SELECTOR).first.wait_for(state="attached")

        last_top_sid = None
        stable_rounds = 0

        for i in range(MAX_SCROLLS):
            top_sid = self._get_top_sid(page)

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

            page.locator(SCROLL_SELECTOR).first.evaluate("el => el.scrollTop = 0")

            # به‌جای sleep خشک، صبر می‌کنیم تا top_sid عوض شود؛
            # اگر نشد، timeout می‌خورد و ادامه می‌دهیم.
            changed = self._wait_for_top_sid_change(
                page,
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

        try:
            print(f"\n🔄 بررسی کانال... ({time.strftime('%H:%M:%S')})")

            context, page = self._open_page()

            try:
                page.goto(CHANNEL_URL, wait_until="domcontentloaded")
                page.locator(MESSAGE_SELECTOR).first.wait_for(state="attached")

                # یک مکث کوتاه برای رندر اولیه؛
                # اگر لازم بود، می‌توانی این را 2 هم نگه داری.
                time.sleep(1)

                self._scroll_to_previous_messages(page, seen_sids)

                # DOM نهایی را می‌گیریم.
                html = page.content()
            finally:
                # بستن context صفحه را کاملاً آزاد می‌کند و حافظه برمی‌گردد.
                try:
                    context.close()
                except Exception as e:
                    print(f"⚠ خطا در بستن context: {e}")

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
            # تا در چرخهٔ بعد یک Chromium سالم ساخته شود.
            self.stop()
            raise


# برای سازگاری با کدهای قدیمی یا استفادهٔ یک‌باره.
# اگر فقط یک‌بار صدا زده شود، Chromium باز و در انتها بسته می‌شود.
def fetch_new_posts(seen_sids: set[str]) -> Iterable[NewsPost]:
    with NewsCollector() as collector:
        yield from collector.fetch_new_posts(seen_sids)


if __name__ == "__main__":
    seen: set[str] = set()

    with NewsCollector() as collector:
        for post in collector.fetch_new_posts(seen):
            print(post)
