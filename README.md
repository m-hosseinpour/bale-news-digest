# Bale News Digest

دریافت خودکار اخبار از کانال بله، دسته‌بندی و خلاصه‌سازی با هوش مصنوعی، و ارسال خلاصه به کانال بله.

## امکانات

- جمع‌آوری پیام‌های جدید کانال با Playwright و Chromium headless
- دسته‌بندی اخبار با OpenAI-compatible API
- خلاصه‌سازی اخبار مهم و ارسال به کانال با بات بله
- ذخیره پیام‌های دیده‌شده در `news_posts.json`
- Webhook برای پاسخ ثابت به پیام‌های خصوصی ربات

## پیش‌نیازها

- Python 3.11+
- uv
- Chromium (بخش «نصب مرورگر» را ببین؛ نیازی به مرورگر سیستمی نیست)

## نصب مرورگر

حالت استاندارد، مرورگر بستهٔ خود Playwright است:

```shell
uv run playwright install --with-deps chromium
```

> **اگر سرور داخل ایران است:** هم CDN رسمی Playwright
> (`cdn.playwright.dev`) و هم مخزن Google برای Chrome for Testing با
> geo-block یعنی `403 Access denied` رد می‌شوند. در این حالت از
> `install_chromium.py` استفاده کن. این اسکریپت همان Chromium را از
> registry پکیج‌های npm برمی‌دارد — پکیج `@sparticuz/chromium` باینری را
> داخل خود tarball دارد، پس به هیچ CDN بلاک‌شده‌ای وابسته نیست:
>
> ```shell
> uv run python install_chromium.py
> ```
>
> خروجی در `~/.cache/playwright-chromium/` می‌نشیند و `config.py` خودش
> پیدایش می‌کند. اگر میرور پیش‌فرض npm کند بود، با `NPM_REGISTRY` عوضش کن:
>
> ```shell
> NPM_REGISTRY=https://registry.npmmirror.com uv run python install_chromium.py
> ```

## نصب پروژه

```shell
uv sync
cp .env.example .env
```

سپس `.env` را ویرایش کن.

حداقل مقادیر لازم:

```env
BALE_BOT_TOKEN=
BALE_BOT_CHAT_ID=
OPEN_AI_API_KEY=
```

اگر از webhook ربات استفاده می‌کنی:

```env
PUBLIC_WEBHOOK_URL=https://your-domain.com/webhook
```

## اجرای اصلی: دریافت و ارسال خلاصه اخبار

اجرای یک‌باره:

```shell
uv run python main.py
```

برای اجرای ساعتی می‌توانی از cron استفاده کنی:

```cron
0 * * * * cd /path/to/project && /path/to/uv run python main.py >> logs/run.log 2>&1
```

## اجرای webhook ربات

برای توسعه:

```shell
uv run flask --app bot_webhook run --host 0.0.0.0 --port 8001
```

برای production:

```shell
uv run gunicorn --bind 127.0.0.1:8001 --workers 1 bot_webhook:app
```

بررسی سلامت سرویس:

```shell
curl http://127.0.0.1:8001/health
```

## ثبت webhook ربات

بعد از اینکه آدرس عمومی webhook با HTTPS آماده شد:

```shell
uv run python set_webhook.py
```

آدرس webhook باید به route زیر برسد:

```text
/webhook
```

## نکات

- خروجی اجرا در لاگ و در `news_posts.json` ذخیره می‌شود.
- اگر سرور RAM کمی دارد، مقادیری مثل `MAX_SCROLLS` و `MAX_DRIVER_REUSE` را در `.env` کمتر کن.
- برای پاسخ‌دهی ربات در PV، حتماً سرور باید با HTTPS در دسترس باشد.
