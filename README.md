# Bale News Digest

دریافت خودکار اخبار از کانال بله، دسته‌بندی و خلاصه‌سازی با هوش مصنوعی، و ارسال خلاصه به کانال بله.

## امکانات

- جمع‌آوری پیام‌های جدید کانال با Selenium و Firefox headless
- دسته‌بندی اخبار با OpenAI-compatible API
- خلاصه‌سازی اخبار مهم و ارسال به کانال با بات بله
- ذخیره پیام‌های دیده‌شده در `news_posts.json`
- Webhook برای پاسخ ثابت به پیام‌های خصوصی ربات

## پیش‌نیازها

- Python 3.11+
- Firefox و geckodriver
- uv

## نصب Firefox و geckodriver

```shell
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:mozillateam/ppa

echo 'Package: *
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001' | sudo tee /etc/apt/preferences.d/mozilla-ppa

sudo apt update
sudo apt install firefox firefox-geckodriver
```

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
