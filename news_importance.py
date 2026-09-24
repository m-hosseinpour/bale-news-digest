"""سنجش اهمیت خبر — تنها قضاوت مدل روی هر پست.

قبلاً دو فراخوانی بود: یکی برای دستهٔ خبری و یکی برای اهمیت (فقط روی دسته‌های
«مهم»). دسته یک پروکسی میانی برای تصمیم ارسال بود و تصمیم نهایی هم با اهمیت
گرفته می‌شد؛ حالا همان یک فراخوانی مستقیم تصمیم می‌گیرد: major می‌رود، بقیه نه.
"""

import re
import time

from config import OPEN_AI_MODEL_NAME
from model import Importance
from open_ai_client_provider import open_ai_client


URL_PATTERN = re.compile(
    r"(https?://\S+|ble\.ir/\S+|www\.\S+)",
    re.IGNORECASE
)

MENTION_PATTERN = re.compile(r"@[\w_]+")
WHITESPACE_PATTERN = re.compile(r"\s+")

# نشانه‌های بولد/ایتالیک مارک‌داون کانال (مثل *تیتر خبر*) که مدل‌ها را به
# دستهٔ اشتباه می‌کشانند.
MARKDOWN_PATTERN = re.compile(r"[*~`]+")

# ایموجی‌ها و انتخابگرهای نمایش. ‌ (نیم‌فاصلهٔ فارسی) عمداً حذف نمی‌شود چون
# بخشی از خود واژه است؛ فقط ‍ (ZWJ) که تقریباً فقط در ایموجی‌ها می‌آید.
EMOJI_PATTERN = re.compile(
    r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿️⃣‍]+"
)

# تعداد تلاش مجدد وقتی پاسخ مدل قابل استفاده نیست: یا خالی است (گیتوی پاسخ
# ۲۰۰ اما بدون choices می‌دهد) یا هیچ برچسب معتبری از فهرست در آن نیست.
MAX_BAD_RESPONSE_RETRIES = 3

# پرامپت روی پست‌های واقعی سنجیده شده (measurements/gate_v2*.json): تبلیغ در
# ۲۵ فراخوانی هیچ‌وقت major نشد، ورزشی/فرهنگی فقط در استثناهای عمدی
# (عنوان بزرگ، مرگ چهرهٔ ملی) و چکیدهٔ چندخبری اهمیت مهم‌ترین خبر داخلش را
# می‌گیرد.
IMPORTANCE_SYSTEM_PROMPT = """You judge how important a Persian news item is, for a reader who has very little time and only wants the news that truly matters.
Output ONLY one word from this list, lowercase, nothing else:
major, normal, trivial

major = a concrete event that ALREADY happened and has real consequences:
- an attack, strike, seizure, bombing, shelling, or armed clash with casualties or damage, or a war escalation;
- a law, ruling, or official decision that took effect;
- a major economic shock: a market crash, a sharp jump in currency, gold, oil, or prices, a record high or low in a market price, a supply or trade cut;
- a disaster: a fatal fire, explosion, flood, earthquake, or a mass-casualty accident;
- the death of a major national figure;
- sports: ONLY a historic national achievement (the national team qualifying for a major tournament, a major title) or a collective disaster involving athletes;
- culture and art: ONLY the death of a nationally known figure, or a cultural event with national consequences.

normal = worth knowing but not urgent: official statements, positions, reactions, speeches, interviews, analyses, predictions, diplomatic meetings, ongoing coverage, routine matches and results, transfers, film/music/festival news, ceremonies and funerals, appointments, budgets, arms deals.

trivial = not really news:
- advertisements and promotions of ANY kind: selling or promoting a product or service, discounts, registration or subscription calls, "contact us", prices and phone numbers, join/invite links, sponsored posts. ALWAYS trivial, even when the wording sounds urgent, official, or news-like.
- daily press reviews and newspaper front-page lists, calendars, vague slogans and metaphors, ceremonial or routine visits, routine personnel news.

If the text is a digest — a list of several separate short news items (for example a "آخرین خبرهای کوتاه" post) — judge the MOST IMPORTANT single item in that list and answer with ITS importance, not with the average of the list.

Most items are normal, not major. Choose major ONLY when the text describes a concrete event that has already happened with consequences. A statement, speech, opinion, prediction, threat, or the announcement of something that WILL happen is NOT major, even when the topic is war, politics, or the economy. An unexplained or unclear incident is normal, not major, until the text itself says what happened and what it cost. Judge only the main news content, not the poster's tone or the emojis.

CRITICAL: Output ONLY the one lowercase word — major, normal, or trivial. No explanation, no punctuation, no list, no extra words. Do not repeat the list of options; write the single word that answers."""


def _clean_text(text: str) -> str:
    text = URL_PATTERN.sub(" ", text)
    text = MENTION_PATTERN.sub(" ", text)
    text = text.replace("|", " ")
    text = MARKDOWN_PATTERN.sub(" ", text)
    text = EMOJI_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def _request_importance(cleaned_text: str) -> str | None:
    """یک فراخوانی مدل؛ None یعنی پاسخ خالی بود (نه خطای شبکه)."""
    response = open_ai_client.chat.completions.create(
        model=OPEN_AI_MODEL_NAME,
        messages=[
            {"role": "system", "content": IMPORTANCE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Text: {cleaned_text}\nAnswer:"},
        ],
        temperature=0.0,
    )

    if not response.choices:
        return None

    content = response.choices[0].message.content
    return content.strip() if content else None


# نفی پیش از برچسب. بدون این گارد، مدل با رد کردن یک برچسب («this is not
# trivial») دقیقاً همان برچسب را به ما می‌دهد و پست به‌اشتباه حذف می‌شود.
_NEGATION_BEFORE_RE = re.compile(r"\b(?:not|no|never|isn'?t|aren'?t|wasn'?t)\s+$")


def _match_importance(raw_output: str) -> Importance | None:
    """برچسب اهمیت را از خروجی خام درمی‌آورد.

    None یعنی هیچ برچسب قابل استنادی نبود (شکست)، که با «اهمیت trivial» فرق
    دارد. تطابق کل‌واژه است و برچسبی که پیش از آن نفی آمده نادیده گرفته
    می‌شود؛ نتیجهٔ نفی‌شده یعنی شکست، پس مسیر retry و در نهایت fail-open.
    """
    text = raw_output.strip().lower()

    for importance in Importance:
        if text == importance.value:
            return importance

    for importance in Importance:
        for match in re.finditer(rf"\b{importance.value}\b", text):
            if not _NEGATION_BEFORE_RE.search(text[: match.start()]):
                return importance

    return None


def judge_importance(news_text: str) -> Importance | None:
    """اهمیت خبر را می‌سنجد؛ None یعنی متن محتوایی نداشت.

    پاسخ خالی/بی‌برچسب و **خطای انتقالی** (timeout، قطع اتصال) هر دو تلاش
    مجدد می‌گیرند: پاسخ بد یعنی مدل از نقش خارج شده، و تپق شبکه‌ای هم نباید
    همان لحظه به fail-open (ارسال) برسد. بعد از تمام‌شدن تلاش‌ها استثنا
    می‌دهد و تصمیم «فرستادن یا نه» با فراخوان‌کننده است.
    """
    cleaned_text = _clean_text(news_text.strip())

    if not cleaned_text:
        return None

    try:
        last_error: Exception | None = None

        for attempt in range(MAX_BAD_RESPONSE_RETRIES + 1):
            try:
                raw_output = _request_importance(cleaned_text)
                last_error = None
            except Exception as e:  # noqa: BLE001 — خطای مدل اینجا «پاسخ بد» است
                last_error = e
                raw_output = None

            importance = _match_importance(raw_output) if raw_output is not None else None
            if importance is not None:
                return importance

            if attempt < MAX_BAD_RESPONSE_RETRIES:
                if last_error is not None:
                    reason = f"خطای {type(last_error).__name__}"
                else:
                    reason = "خالی" if raw_output is None else "بدون برچسب معتبر"
                print(
                    f"⚠ {reason} از مدل در سنجش اهمیت؛ تلاش دوباره "
                    f"({attempt + 1}/{MAX_BAD_RESPONSE_RETRIES})"
                )
                time.sleep(1)

        if last_error is not None:
            raise RuntimeError(f"تماس با مدل پس از چند تلاش ناموفق بود: {last_error}")
        raise RuntimeError("مدل پس از چند تلاش اهمیت معتبری برنگرداند")

    except Exception as e:
        print(f"خطا در سنجش اهمیت: {e}")
        raise e
