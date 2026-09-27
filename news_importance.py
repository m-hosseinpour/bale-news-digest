"""سنجش اهمیت خبر — تنها قضاوت مدل روی هر پست.

قبلاً دو فراخوانی بود: یکی برای دستهٔ خبری و یکی برای اهمیت (فقط روی دسته‌های
«مهم»). دسته یک پروکسی میانی برای تصمیم ارسال بود و تصمیم نهایی هم با اهمیت
گرفته می‌شد؛ حالا همان یک فراخوانی مستقیم تصمیم می‌گیرد: major می‌رود، بقیه نه.
"""

import re
import time

from config import OPEN_AI_MODEL_NAME
from model import Importance
from open_ai_client_provider import ModelAnswer, describe_answer, open_ai_client


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

# این پرامپت دو چیز را اجبار می‌کند (تبلیغ همیشه trivial، خبر ورزشی غیرمهم
# trivial) و یک سختگیری کلی می‌گذارد: فقط چیزِ «تازه» می‌تواند major باشد؛
# گذشته‌نگر (سالگرد، «به مناسبت …»، آرشیو، بازگویی واقعهٔ قدیم) در بهترین حالت
# normal است؛ بیشتر خبرها major نیستند و در شک باید برچسب پایین‌تر را گرفت.
# بقیهٔ قضاوت با خود مدل است — تعریف مثبتِ major و فهرست normal عمداً نیستند.
#
# دو سنجش، هر دو یک قرعه در ۲۷ سپتامبر:
# - نسخهٔ آزاد روی ۴۶ پست (measurements/free_gate_after.json): تبلیغ ۱۰/۱۰ و
#   ورزشی روتین ۸/۸ trivial ماندند و ۱۰ از ۱۶ بیانیه major شد، ولی ۴ رویداد
#   مشخص که پرامپت قبلی همیشه major می‌فرستاد normal برگشتند (عبور نفت برنت از
#   ۱۰۵ دلار، رکورد گازوئیل اروپا، پیشروی ترکیه در شمال عراق، بارگیری مخفی
#   نفت‌کش‌ها) — فهرست‌های پرامپت قبلی فقط سقف نبودند، تعریف مثبتِ major هم
#   بودند.
# - پس از افزودن بند سختگیری، روی ۱۳ پست (measurements/strict_gate_after2.json):
#   هر دو پست سالگردِ نصرالله trivial شدند (پیش‌تر major رفته بودند)، تبلیغ ۲/۲
#   trivial ماند، ۳ رویداد از آن ۴ برگشتند و بیانیه‌های صعودکرده به normal
#   برگشتند. هزینه: گزارشی مثل «تصاویری از حملات جدید پاکستان…» که پیامدش را در
#   متن نمی‌گوید normal می‌شود، نه major.
IMPORTANCE_SYSTEM_PROMPT = """You judge how important a Persian news item is, for a reader who has very little time and only wants the news that truly matters.
Output ONLY one word from this list, lowercase, nothing else:
major, normal, trivial

major = a news item that the reader should know right now, even if they read nothing else today.
normal = worth knowing but not urgent.
trivial = not really news.

Judge the news itself, not its topic, and remember that only something NEW can be major: something that has just happened, or has just been announced, with a real consequence. A retrospective is not news — an anniversary or commemorative post, an item published «به مناسبت …» or marking a past event, archive or file material, a repost or a re-telling of an old event, or a piece about the past. These are normal at best, and trivial when they carry no new fact at all.

Most items are not major. Choose major only when the reader would be worse off today for not knowing it. When the text leaves you unsure between two labels, choose the lower one.

Two rules always apply, whatever the text sounds like:
- Advertisements and promotions of ANY kind are trivial: selling or promoting a product or service, discounts, registration or subscription calls, "contact us", prices and phone numbers, join/invite links, sponsored posts. ALWAYS trivial, even when the wording sounds urgent, official, or news-like.
- Sports: a routine match or result, a league or federation matter, a transfer, an athlete's statement, a press review, or a small tournament is trivial. Only a genuinely big sports story — a historic national achievement, or a real disaster involving athletes — may be judged higher.

Everything else is your own judgment: decide how important the item really is from what the text actually says, and not from the kind of topic it is.

If the text is a digest — a list of several separate short news items (for example a "آخرین خبرهای کوتاه" post) — judge the MOST IMPORTANT single item in that list and answer with ITS importance, not with the average of the list.

CRITICAL: Output ONLY the one lowercase word — major, normal, or trivial. No explanation, no punctuation, no list, no extra words. Do not repeat the list of options; write the single word that answers."""


def _clean_text(text: str) -> str:
    text = URL_PATTERN.sub(" ", text)
    text = MENTION_PATTERN.sub(" ", text)
    text = text.replace("|", " ")
    text = MARKDOWN_PATTERN.sub(" ", text)
    text = EMOJI_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def _request_importance(cleaned_text: str) -> ModelAnswer:
    """یک فراخوانی مدل؛ متن None یعنی پاسخ خالی بود (نه خطای شبکه)."""
    response = open_ai_client.chat.completions.create(
        model=OPEN_AI_MODEL_NAME,
        messages=[
            {"role": "system", "content": IMPORTANCE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Text: {cleaned_text}\nAnswer:"},
        ],
        temperature=0.0,
    )

    if not response.choices:
        return ModelAnswer(None, None)

    choice = response.choices[0]
    content = choice.message.content
    text = content.strip() if content else None
    return ModelAnswer(text, choice.finish_reason)


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
        last_answer: ModelAnswer | None = None

        for attempt in range(MAX_BAD_RESPONSE_RETRIES + 1):
            try:
                last_answer = _request_importance(cleaned_text)
                last_error = None
            except Exception as e:  # noqa: BLE001 — خطای مدل اینجا «پاسخ بد» است
                last_error = e
                last_answer = None

            raw_output = last_answer.text if last_answer is not None else None
            importance = _match_importance(raw_output) if raw_output is not None else None
            if importance is not None:
                return importance

            if attempt < MAX_BAD_RESPONSE_RETRIES:
                if last_error is not None:
                    reason = f"خطای {type(last_error).__name__}: {last_error}"
                else:
                    reason = "خالی" if raw_output is None else "بدون برچسب معتبر"
                print(
                    f"⚠ {reason} از مدل در سنجش اهمیت "
                    f"({describe_answer(last_answer)}); تلاش دوباره "
                    f"({attempt + 1}/{MAX_BAD_RESPONSE_RETRIES})"
                )
                time.sleep(1)

        if last_error is not None:
            raise RuntimeError(f"تماس با مدل پس از چند تلاش ناموفق بود: {last_error}")
        raise RuntimeError(
            "مدل پس از چند تلاش اهمیت معتبری برنگرداند "
            f"({describe_answer(last_answer)})"
        )

    except Exception as e:
        print(f"خطا در سنجش اهمیت: {e}")
        raise e
