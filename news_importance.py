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
from post_time import format_post_time


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

# این پرامپت دو چیز را از پیش پایین می‌آورد (تبلیغ همیشه trivial، خبر ورزشی
# غیرمهم trivial) و یک دسته را از پیش بالا می‌برد (رویداد تازهٔ نبرد و بیانیهٔ
# مقام ارشد دربارهٔ جنگ در ایران و منطقه همیشه major) و یک سختگیری کلی
# می‌گذارد: فقط چیزِ «تازه» می‌تواند major
# باشد؛ گذشته‌نگر (سالگرد، «به مناسبت …»، آرشیو، بازگویی واقعهٔ قدیم) در بهترین
# حالت normal است؛ بیشتر خبرها major نیستند و در شک باید برچسب پایین‌تر را گرفت —
# جز خبر جنگ که بند خودش را دارد. بقیهٔ قضاوت با خود مدل است؛ فهرست normal
# عمداً نیست و تنها موضوعی که از پیش major می‌شود همان بند جنگ است.
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
# - نسخهٔ سوم (۳۰ سپتامبر) دو تغییر داد: «پیامد واقعی» به پیامد برای همین
#   خواننده گره خورد — خبر بزرگِ داخلیِ کشورهای دیگر (سیاست داخلی، دادگاه،
#   انتخابات، علم و فضا) اینجا major نیست — و فهرست گذشته‌نگر «خاطره و روایت
#   اول‌شخص از واقعهٔ گذشته» را هم گرفت. سنجش روی ۳۱ پست ۷ مهر، دو قرعه، کنار
#   فایل قبل و ۱۱ پست کنترل (measurements/review929_before.json و
#   review929_after.json): هر ۸ کنترلِ major و هر ۳ کنترلِ trivial دست‌نخورده
#   ماندند؛ روی ۲۰ پست مورد اختلاف، major از ۲۳ قرعه از ۴۰ به ۱۶ افتاد — ۶
#   ارسال زائد پایین آمد (روایت مک‌گورک به normal/trivial، آتش‌سوزی تهران،
#   کناره‌گیری مقام دادگستری آمریکا، دعوای CNN با کاخ سفید، استارشیپ، هشدار
#   سیلاب) و ۳ جاماندهٔ مشخص بالا آمد (نیروگاه روساتم، سفر نتانیاهو به ابوظبی،
#   گزارش المیادین). هزینهٔ باقی‌مانده: دو پست هنوز در یک قرعه از دو قرعه major
#   می‌شوند (شایعهٔ صدام حفتر، هشدار نارنجی هوا) و یک بیانیهٔ دکترینی ارتش هم
#   major شد. مدل روی خبرِ بیگانه گاهی تا trivial پایین می‌رود در حالی که normal
#   درست‌تر است؛ با آستانهٔ فعلی (major) این بر تصمیم ارسال اثری ندارد.
# - نسخهٔ چهارم (۱۶ نوامبر ۲۰۲۶) به درخواست کاربر یک بند جدا برای خبر جنگ گذاشت:
#   هر «رویداد تازه» در نبردِ ایران یا منطقه — حمله، گلوله‌باران، درگیری، موشک یا
#   پهپاد شلیک‌شده/ساقط‌شده، جابه‌جایی نیرو و شناور، تلفات و خسارت نبرد، آتش‌بس و
#   نقضش — همیشه major است، هرچند گزارش کوتاه باشد یا پیامدش را ننویسد؛ خودِ
#   درگیری پیامد برای این خواننده است. در آن نسخه بیانیه، تهدید، پیش‌بینی،
#   تحلیل و گذشته‌نگر جنگی (خاطره، سالگرد، مرور جنگ) همان قاعدهٔ عادی را
#   داشتند (بند بعدی بیانیهٔ مقام ارشد را جدا کرد).
#   سنجش روی ۲۰ پست، دو قرعه (war_gate.sids.json؛ قبل war_gate_before.json، بعد
#   war_gate_after.json): ۷ از ۸ رویداد جنگیِ normal (حملهٔ موشکی یمن به مواضع
#   سعودی، درگیری کرکوک، گلوله‌باران جنوب لبنان، انهدام انبارهای سعودی، انهدام
#   تیم پژاک در مرز، ساقط‌شدن پهپاد در غرب ایران، «صدای انفجار» قشم) در هر دو
#   قرعه major شدند؛ ۳ تهدید لفظی، تبلیغ، ورزش و جنگ اوکراین تکان نخوردند، هیچ
#   گذشته‌نگر جنگی major نشد (یکی یک قرعه پایین‌تر رفت) و ۲ کنترل major هم major
#   ماندند. تنها جامانده: انفجار بی‌توضیح بغداد. هزینه: «صدای انفجار» تأییدنشده
#   در ایران حالا major می‌شود. سنجش تکی روی ۵ پست دیگر
#   (war_gate_probe_after.json): ۲ از ۵ بالا رفت — حملهٔ تازه به رادار آمریکا در
#   بحرین (درست) و پوشش تصویری عملیات یمن در مأرب که تازه‌بودنش از متن معلوم
#   نیست (یعنی ۱ از ۳ پست تصویریِ گذشته‌نگر بالا رفت) — و تصاویر خرابه‌های قدیمی و
#   انفجار کارخانهٔ ترکیه normal ماندند.
#   پس از بازبینی، جملهٔ «even when it is one-sided» تیزتر شد تا ادعای یک‌طرفه
#   دربارهٔ رویدادی که رخ داده با تهدید/پیش‌بینی/تحلیل/تکذیب قاطی نشود؛ بازآزمون
#   روی ۱۱ پست یک قرعه (war_gate_recheck_after.json) همان الگو را داد (ادعای
#   یک‌طرفهٔ یمن major، بیانیه‌ها normal، تبلیغ و ورزش trivial، حملهٔ تازهٔ بحرین
#   major، هیچ پست تصویریِ گذشته‌نگر — مأرب، پایگاه سلطان، ویرانهٔ پایگاه‌های
#   آمریکا — major نشد) و دو مورد مبهم با دو قرعهٔ بیشتر
#   (war_gate_recheck_after2.json): «صدای انفجار» قشم ۲ از ۳ major و انفجار
#   بی‌توضیح بغداد ۲ از ۳ normal.
# - نسخهٔ پنجم (۱۷ نوامبر ۲۰۲۶) بند جنگ را به بیانیه‌ها هم گسترد: هر حرف تازهٔ
#   یک مقام ارشد دربارهٔ جنگِ ایران و منطقه — رئیس کشور یا دولت (رئیس‌جمهور،
#   نخست‌وزیر، پادشاه، رهبر)، وزیر خارجه یا دفاع، فرماندهٔ ارشد، سخنگوی رسمی، یا
#   رهبر گروه مسلح درگیر، از ایران یا کشورهای منطقه یا گروه مسلح درگیر یا قدرت
#   بزرگ دخیل — حتی وقتی
#   فقط حرف است (موضع، هشدار، تهدید، وعدهٔ پاسخ، شرط، تصمیم) major است. کسی که
#   الان چنین مقامی دارد حتی اگر روحانی هم باشد حساب می‌شود؛ کسی که تنها
#   ادعایش مقام گذشته است نه.
#   نمایندهٔ مجلس، روحانیِ بی‌مقام، کارشناس، خبرنگار و تحلیلگر، تکرار حرف قدیمی،
#   نقل‌قول بی‌منبع و تفسیر حرف دیگران همان قاعدهٔ عادی را دارند.
#   سنجش روی ۱۸ پست، دو قرعه (war_stmt.sids.json؛ قبل war_stmt_before.json، بعد
#   war_stmt_after.json): ۷ از ۸ بیانیهٔ مقام ارشد (تهدید رضایی به پایگاه‌های
#   اروپایی، برداشتن محدودیت‌ها، عبداللهی زیر بمباران، حیدری و قرارگاه ناوها،
#   ایزدی، سخنگوی ارتش، عراقچی «فراتر از ایران») از normal 2/2 به major 2/2
#   رفت. هشتم، حرف نعیم قاسم دربارهٔ بهانه‌های هستهای (نه دربارهٔ نبرد)، فقط یک
#   قرعه از دو major شد و در واژگان بعدی normal 2/2 ماند. ۵ صدای غیرمقامی (پنس و
#   بلینکنِ سابق، نمایندهٔ کنگره، کارشناسان چینی، تحلیل آتلانتیک) هیچ‌کدام major
#   نشدند و گذشته‌نگر، تبلیغ، ورزش، اوکراین و کنترل major هم جابه‌جا نشدند.
#   قرعهٔ نگهبان روی ۱۲ پست جنگی (war_stmt_guard_after.json): از ۹ رویداد، ۸ همان
#   major ماندند و فقط انفجار بی‌توضیح بغداد normal شد؛ دو تهدید فرماندهٔ ارشد
#   (ایزدی، رضایی) major شدند و حرف پنس (معاون سابق) normal ماند. با واژگان
#   نهایی همین نگهبان یک قرعه (war_stmt_guard_final.json) ۱۱ از ۱۲ را major داد و
#   این بار بغداد هم major شد — همان مورد مبهم همیشگی.
#   سپس دامنهٔ مقام‌ها به رئیس کشور/دولت و رهبر گروه مسلح و قاعدهٔ تقدم بر
#   روحانی باز شد: ۶ پست رئیسان و وزرا، دو قرعه (war_stmt2_before/after.json).
#   نخست‌وزیر انگلیس major 2/2 (قبل هم بود؛ با واژگان نهایی دوباره سنجیده نشد)،
#   رهبر انقلاب از major/normal به major 2/2، لاوروف دربارهٔ ایران major ۱ از ۲،
#   و در عوض نخست‌وزیر اسپانیا (کشور بیرون منطقه و غیردخیل) normal 2/2 و لاوروف
#   دربارهٔ اوکراین normal 2/2. زیر واژگان نهایی ۸ پست سنجیده شد — همان ۵ پستِ
#   این مجموعه به‌علاوهٔ قاسم، پنس و تبلیغ به‌عنوان کنترل (war_stmt3_after.json) —
#   و دو بیانیهٔ اردوغان دربارهٔ همین جنگ major 2/2 شد (war_stmt4_after.json)،
#   یعنی شاخهٔ رئیس دولتِ منطقه کار می‌کند. پست نتانیاهو زیر major ماند، ولی
#   دلیلش قید «حرف تازه» است نه جغرافیا: خودِ کانال آن را «عملیات روانی
#   انتخاباتی» توصیف کرده و در واژگان میانی یک قرعه major شده بود.
IMPORTANCE_SYSTEM_PROMPT = """You judge how important a Persian news item is, for a reader who has very little time and only wants the news that truly matters. This reader follows Iran — its security, its war and diplomacy, its economy and the prices people pay — and the region around it.
Output ONLY one word from this list, lowercase, nothing else:
major, normal, trivial

major = a news item that the reader should know right now, even if they read nothing else today.
normal = worth knowing but not urgent.
trivial = not really news.

Judge the news by what it actually does, not by its topic, and remember that only something NEW can be major: something that has just happened, or has just been announced, with a real consequence for this reader. A retrospective is not news — an anniversary or commemorative post, an item published «به مناسبت …» or marking a past event, archive or file material, newly released footage or images of an event that happened well before this post, a repost or a re-telling of an old event, a memoir, or a first-person account in which someone recounts what happened at some earlier time. These are normal at best, and trivial when they carry no new fact at all.

The consequence has to be a consequence for THIS reader, not merely a dramatic story somewhere. What happens to Iran, or to the war, the negotiations, oil, the currency or the prices the reader pays, is major. A big story inside another country's own affairs — its domestic politics, its courts, its elections, its science or space programme — is not major here, however loudly it is reported there, unless it changes something for Iran or for this region.

War is the exception, and war news from Iran and this region never takes the lower label. When the item reports a NEW development in the fighting in Iran or this region — an attack, strike, shelling, raid or exchange of fire; a missile or drone launched, intercepted or shot down; fighters, troops, ships or aircraft moved or deployed for a fight; casualties, damage or captures caused by fighting; a ceasefire reached, violated or broken — judge it major, however brief the report is, even when it does not spell out what happens next; the fighting itself is the consequence for this reader. A fresh statement about the war in Iran and this region by a senior official is major in the same way, even when it is only words: what a head of state or government — a president, a prime minister, a monarch or a supreme leader — a foreign or defence minister, a senior military commander, an official spokesman, or the leader of an armed group fighting here says counts, whether it is a position, a warning, a threat, a promise of response, a condition or a decision. The speaker has to speak for Iran, a state in this region, an armed group fighting here, or a great power involved in this war. Someone who holds such an office now counts even if they are also a cleric; someone whose only claim is a past office does not. What decides a development is whether the text reports something the fighting has done: a one-sided claim that an attack, shelling, interception, hit or ceasefire did happen is still that development. Not every voice counts: a member of parliament, a cleric without such an office, an expert, a journalist or an analyst talking about the war, a re-run of an old statement, an unsourced quote, and commentary about what someone said follow the ordinary rules above, as do a denial that anything happened, and a memoir, first-person account or anniversary of a past war.

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


def _published_note(published_ms: int | None) -> str:
    """بلوکِ «تاریخ انتشار» — صریحاً متادیتا، نه بخشی از متن خبر."""
    if published_ms is None:
        return ""
    return (
        "CONTEXT ABOUT THIS POST — METADATA, NOT PART OF THE NEWS TEXT.\n"
        f"It was published on {format_post_time(published_ms)}.\n"
        "Use it only to judge whether what the text reports is new or already old: an event the text "
        "dates well before this publication date is not new, and footage or images of it released now "
        "do not make it new.\n\n"
    )


def _request_importance(cleaned_text: str, published_ms: int | None = None) -> ModelAnswer:
    """یک فراخوانی مدل؛ متن None یعنی پاسخ خالی بود (نه خطای شبکه)."""
    response = open_ai_client.chat.completions.create(
        model=OPEN_AI_MODEL_NAME,
        messages=[
            {"role": "system", "content": _published_note(published_ms) + IMPORTANCE_SYSTEM_PROMPT},
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


def judge_importance(news_text: str, published_ms: int | None = None) -> Importance | None:
    """اهمیت خبر را می‌سنجد؛ None یعنی متن محتوایی نداشت.

    `published_ms` زمان انتشار پست است تا مدل بتواند تاریخِ داخل متن را با آن
    بسنجد؛ بدون آن، «حالا» برای مدل تعریف‌شده نیست و رویداد قدیمی تازه دیده می‌شود.

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
                last_answer = _request_importance(cleaned_text, published_ms)
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
