# گزارش ریفکتور جمع‌آوری خبر (Playwright/Chromium → API عمومی بله)

برنچ: `refactor/collector-api` · تاریخ: ۱۴۰۵/۰۷/۰۱ (2026-09-23) · بدون push (طبق بریف، تصمیم با هماهنگ‌کننده)

## ۱. فایل‌های عوض‌شده

| فایل | تغییر |
|---|---|
| `news_collector.py` | بازنویسی کامل: حذف `NewsCollector`، Playwright، BeautifulSoup، سلکتورهای CSS و کل منطق اسکرول. جایگزین با `resolve_peer_id` · `load_history` · `extract_text` · `normalize_news_text` · `fetch_new_posts` (ماژول‌سطح، generator). |
| `config.py` | حذف `CHANNEL_URL`, `MAX_SCROLLS`, `SCROLL_PAUSE`, `HEADLESS`, `DISABLE_IMAGES`, `PAGE_LOAD_TIMEOUT`, `WEBDRIVER_WAIT_TIMEOUT`, `MAX_DRIVER_REUSE`, `CHROMIUM_EXECUTABLE_PATH`, `_env_bool`. افزودن `CHANNEL_SLUG`, `PEER_ID` (از env، بدون شبکه در import)، `MAX_PAGES_PER_RUN`, `MAX_POSTS_PER_RUN`, `HISTORY_PAGE_SLEEP`, `HTTP_TIMEOUT` و `_env_float`. |
| `main.py` | حذف بلوک `with NewsCollector() as collector:` و import مربوطه؛ فراخوانی مستقیم `fetch_new_posts(seen_sids)`. |
| `news_summarizer.py` | `BALE_POST_LINK_TEMPLATE` از `CHANNEL_SLUG` ساخته می‌شود. منطق `_post_link` دست‌نخورده. |
| `scripts/resolve_peer_id.py` | جدید: کشف یک‌بارهٔ آیدی داخلی کانال برای گذاشتن در `.env`. |
| `scripts/verify_collector.py` | جدید: شمارش نوع پیام‌ها، پوشش استخراج متن، نرخ تطبیق `sid`. قابل اجرای مجدد. |
| `tests/` (۶ فایل، ۶۱ تست) | جدید؛ pytest، بدون شبکه. |
| `pyproject.toml` + `uv.lock` | حذف `beautifulsoup4`, `brotli`, `playwright`؛ افزودن pytest در `[dependency-groups] dev`؛ `pythonpath=["."]` و `testpaths=["tests"]`. |
| `install_chromium.py` | حذف کامل فایل. |
| `.github/workflows/deploy.yml` | حذف مرحلهٔ `uv run python install_chromium.py` و کامنت توضیحی‌اش. |
| `.env` / `.env.example` | کلیدهای Playwright/scroll حذف؛ `CHANNEL_SLUG` و `PEER_ID` اضافه. در `.env.example` مقدار `PEER_ID` فقط نمونه است. هیچ مقدار رازی خوانده/چاپ/کامیت نشد. |
| `CLAUDE.md` | خط Main-Flow به‌روز شد؛ بولت Chromium/geo-block حذف و با تله‌های caption و anchor عوض شد؛ بخش Common Commands و یادداشت خطای شبکه اضافه شد. |
| `README.md` | بخش «نصب مرورگر» و پیش‌نیاز Chromium کامل حذف شد؛ `CHANNEL_SLUG`/`PEER_ID` مستند شد؛ روش کشف peer id و بخش تست/verify اضافه شد. |

## ۲. معماری جدید در سه خط

۱. `config.PEER_ID` از env خوانده می‌شود و `fetch_new_posts` بدون هیچ کشف مجدد یا تماس شبکه‌ای جز `LoadHistory` کار می‌کند.
۲. هر صفحه با `POST https://api.ble.ir/api/v1/LoadHistory` با `{"peer":{"type":2,"id":PEER_ID},"date":anchor}` می‌آید (اندازهٔ صفحه ثابت ۱۰)، اعتبارسنجی می‌شود، و `anchor` بعدی `min(date) - 1` است.
۳. متن هر پیام از `textMessage.text` یا `documentMessage.caption.text` استخراج، امضای کانال حذف، دسته‌بندی و به‌شکل `NewsPost(sid=f"{rid}-{date}")` yield می‌شود.

## ۳. اعداد تأیید (بخش ۶ بریف)

### ۶.۱ شمارش پیام‌ها به تفکیک نوع — `uv run python scripts/verify_collector.py 100`

```
documentMessage      72  (72%)
textMessage          21  (21%)
emptyMessage          7  (7%)

documentMessage با caption غیرخالی: 49 از 72
متن غیرخالی بعد از normalize:        70 از 100
```

`documentMessage` بخش عمده است (۷۲٪) و ۴۹ تای آن متن دارد — یعنی caption درست خوانده می‌شود. عدد ۷۰ از ۱۰۰ با ۷۲ documentMessage سازگار است (۴۹ caption + ۲۱ textMessage = ۷۰؛ ۲۳ سند بدون caption و ۷ emptyMessage متن ندارند و درست رد می‌شوند).

بررسی تکمیلی روی یک نمونهٔ دوم ۱۰۰ پیامی: `documentMessage 71, textMessage 21, emptyMessage 8`؛ ۵۵ سند caption داشت، ۱۶ سند caption خالی بود، و ۴۸ متن شامل خط تبلیغاتی واقعی `@Akharinkhabar | akharinkhabar.ir` بودند (حرف A بزرگ، اسلاگ کوچک) — این عدد تفاوت بزرگی/کوچکی را تأیید می‌کند.

### ۶.۲ اثبات سازگاری dedup

نرخ تطبیق `sid` روی ۱۰۰ پیام آخر: **۶۴ از ۷۰ sid غیرخالی (۹۱٪)** با `news_posts.json` موجود (۱۰۰۰ پست، ۴۹۱ تای آن‌ها rid منفی) مطابقت دارد — بالای آستانهٔ ۹۰٪ که بریف انتظار داشت.

اجرای آزمایشی با `seen_sids` واقعی از `news_posts.json`:

```
seen_sids from news_posts.json: 1000
posts offered as NEW: 6
of those, already in news_posts.json (would be re-sends): 0
  ✓ به آخرین پست قبلی رسیدیم (sid=-5395742309641863192-1790163720319)
```

هیچ پست تکراری‌ای پیشنهاد نشد و توقف زودهنگام روی اولین sid دیده‌شده کار کرد (rid منفی درست تطبیق خورد).

### ۶.۳ مسیر dry جمع‌آوری → دسته‌بندی → خلاصه‌سازی (بدون ارسال)

`fetch_new_posts` با سقف ۳ پست، روی خروجی واقعی، بدون هیچ فراخوانی `send_message`:

```
[ war_conflict ]  sid=6071979416868994035-1790164654825   len(text)=199
MESSAGE-WOULD-SEND:
یک منبع آگاه از انجام عملیات ویژه ... همچنان ادامه دارد.
لینک خبر مرجع:
https://ble.ir/akharinkhabar/6071979416868994035/1790164654825

[ war_conflict ]  sid=2200237794720351565-1790164636162   len(text)=130
MESSAGE-WOULD-SEND:
*وقوع یک حادثه دریایی در تنگه هرمز* ...

[ politics ]  sid=-9069143990870132853-1790164621986   len(text)=80
MESSAGE-WOULD-SEND:
* تصاویری از فارغ التحصیلی نخستین گروه پلیس زن سوریه ...*

collected=3
```

**مرز E2E رعایت شد:** `main.py` با ارسال واقعی اجرا نشد و `test.py` اجرا نشد. ارسال واقعی به کانال پروداکشن تصمیم هماهنگ‌کننده/کاربر است.

### ۶.۴ عدم‌وابستگی به مرورگر

```
$ uv run python -c "import playwright"   → ModuleNotFoundError: No module named 'playwright'
$ uv run python -c "import bs4"          → ModuleNotFoundError: No module named 'bs4'
```

و با همین محیط (بدون playwright/bs4 نصب‌شده) واکشی واقعی انجام شد: یک صفحهٔ کامل ۱۰ پیامی، و در مسیر dedup بالا کل صفحه‌بندی تا رسیدن به پست دیده‌شده پیش رفت. یعنی جمع‌آوری بدون مرورگر کار می‌کند.

### ۶.۵ پاک‌سازی

```
$ grep -rn "playwright|Chromium|BeautifulSoup|MessageItem_messageWrapper|selenium" .
README.md:18:نیازی به مرورگر، Chromium یا Playwright نیست: جمع‌آوری از طریق
```

تنها نتیجهٔ زنده جمله‌ای در README است که می‌گوید مرورگر لازم **نیست**. هیچ ارجاع کد/وابستگی/CI باقی نمانده.

### تست‌ها

```
$ uv run pytest -q
61 passed in 1.94s
```

پوشش: `extract_text` برای هر ۵ حالت (textMessage، documentMessage با caption، caption خالی، کلید caption غایب، emptyMessage) و شکل‌های بدشکل؛ اعتبارسنجی `load_history` روی payload نامعتبر/`history` غیرلیست/`rid` و `date` نامعتبر؛ گارد anchor؛ گارد توقف صفحه‌بندی؛ `sid` با rid منفی دست‌نخورده؛ `normalize_news_text` روی متن واقعی تبلیغاتی (تطبیق بی‌توجه به بزرگی/کوچکی) و بی‌اثر بودن روی متن ناهمبسته؛ رگرسیون‌پین `_post_link`؛ و رفتار generator (`fetch_new_posts`) شامل سقف صفحه/پست و بالا رفتن خطای شبکه.

## ۴. آنچه حذف شد

- کلاس `NewsCollector` و کل چرخهٔ عمر مرورگر (start/stop/restart/`_launch_browser`/`_open_page`).
- کل منطق اسکرول (`_scroll_to_previous_messages`، `_wait_for_top_sid_change`، `_get_top_sid`) و سلکتورهای CSS هش‌شده.
- `_extract_raw_posts` و استفاده از BeautifulSoup و `page.content()`.
- وابستگی‌های `playwright`, `beautifulsoup4`, `brotli` از `pyproject.toml` و `uv.lock`.
- فایل `install_chromium.py` و مرحلهٔ CI مربوط به آن.
- کلیدهای Playwright/scroll از `.env` و `.env.example` و بخش «نصب مرورگر» و پیش‌نیاز Chromium از README و بولت geo-block از `CLAUDE.md`.
- `_env_bool` (پس از حذف `HEADLESS`/`DISABLE_IMAGES` بی‌مصرف شد).

## ۵. چیزهایی که نتوانستم تأیید کنی

۱. **ارسال واقعی انتها-به-انتها (بند ۶.۳ بریف).** طبق «مرز E2E» بریف عمداً اجرا نشد؛ فقط مسیر collect → classify → summarize → compose اجرا و خروجی واقعی ضبط شد. فراخوانی `send_message` تأیید نشده است.
۲. **`main.py` کامل.** به دلیل بند بالا اجرا نشد؛ فقط import و مسیر تا `compose_message` تأیید شده است.
۳. **مقایسهٔ «قبل و بعد» به معنای دقیق.** جمع‌آوری قبلی مبتنی بر مرورگر بود و امکان اجرای آن برای گرفتن شمارش «قبل» وجود نداشت (playwright دیگر نصب نیست و اسکرپ مرورگری هم روی این ماشین اجرا نشد). اعدادی که در بخش ۶.۱ آمده‌اند از API واقعی، و برای یک نمونهٔ دو‌باره، اندازه‌گیری شده‌اند.
۴. **پایداری بلندمدت `PEER_ID` و قرارداد API.** این API مستندنشده است؛ اعتبارسنجی فقط شکل پاسخ را در زمان اجرا قفل می‌کند، نه تغییرات آیندهٔ سرور را.
۵. **یک انحراف آگاهانه از متن بریف:** بریف می‌گفت «اگر `min(date) - 1 >= anchor` بود raise کن». این شرط با `date` شاملِ anchor، برای هر صفحهٔ معتبر با جدیدترین پیام دقیقاً روی anchor هم برقرار می‌شود و اجرای عادی را می‌شکست. شرط به `min(date) > anchor` تغییر کرد (= «anchor اکیداً پیش نرفت») و چون این تنها حالتِ «عدم پیشرفت» با `date` معتبر است، پوشش همان است؛ برای اینکه تلهٔ «جا افتادن منهای یک» هم بی‌صدا نماند، گارد دومی اضافه شد که اگر صفحهٔ بعدی هیچ rid ندیده‌ای نداشته باشد خطا می‌دهد (تست‌شده). در `REFACTOR_REPORT` همین‌جا ثبت شده تا اگر بریف در این مورد سخت‌گیر است، قابل بازبینی باشد.
۶. **`SUMMARIZE_BATCH` در `.env`** با هیچ کدی در ریپو مطابقت ندارد (قبل از این ریفکتور هم همین‌طور بود). چون خارج از دامنه بود دست نخورد.
