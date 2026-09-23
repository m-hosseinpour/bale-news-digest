import re
import time

from config import OPEN_AI_MODEL_NAME
from model import NewsCategory
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

# تعداد تلاش مجدد وقتی گیتوی پاسخ ۲۰۰ اما بدون choices برمی‌گرداند.
MAX_EMPTY_RESPONSE_RETRIES = 3

SYSTEM_PROMPT = """You are a strict Persian news classifier. Output EXACTLY ONE lowercase label from this list and nothing else:
war_conflict, advertisement, politics, economy, social, sports, culture_art, science_tech, unknown

CORE RULES:
1. Ignore emojis, URLs, join links, @mentions, channel names, and repeated boilerplate. Classify only the main meaningful news text.
2. Do NOT choose unknown just because the text is short, ambiguous, missing a cause, or contains links. Choose the best news category.
3. Use unknown ONLY if there is no meaningful news content, for example empty text, only links/emojis, or completely unintelligible text.
4. If two categories are possible, choose the category that matches the main subject/entity, not a secondary detail. The speaker's title (minister, spokesperson, president, commander) is NEVER a category on its own — it only sets context. The actual subject of the news decides the category. A cabinet decision on pensions is economy; a presidential decree on a military operation is war_conflict.
   - An official's ordinary visit, presence, or movement for a diplomatic or UN event (arriving, entering a building, attending a summit, or going somewhere to give a speech) is politics. This is war_conflict ONLY if the text itself describes a military action, strike, attack, or an official armed-forces statement about combat.
5. Sanctions, embargoes, and economic isolation rule:
   - Choose politics when the news is about a government decision, official statement, diplomatic protest, or international dispute over sanctions/embargoes/economic isolation — even when the words "sanction" or "economic" appear in the text.
   - Choose economy only when the news is about the MARKET EFFECT of sanctions: price changes, trade volume, currency moves, supply disruptions, or business impacts.
   - A government's decision to impose, lift, join, withdraw from, or protest sanctions/embargoes is politics, not economy — even if the words "oil", "trade", or "imports" appear.
   - The mere mention of "sanctions" or "economic isolation" does NOT make it economy. Ask: is this news about a political/diplomatic act, or about prices/markets/trade flows?
6. Security/military & Locations rule:
   - Choose war_conflict for any of the following:
     * an actual military action, attack, strike, seizure, armed clash, or explicit security incident;
     * official military statements, commanders' messages, or armed forces communiqués about combat readiness, deterrence, defense/offense doctrine, interception capability, electronic/cyber warfare capability, air defense, missile/radar posture, or the ability to counter enemy threats — even when no specific attack is happening;
     * unexplained disruptions in conflict-prone regions (e.g., Jeddah airport, Red Sea incidents).
   - HOWEVER, mentions of strategic locations (Strait of Hormuz, borders, seas) DO NOT automatically mean war_conflict. If the text is about the situation of citizens, fishermen, sailors, trade, or weather in these areas, choose social or economy.
   - politics covers ONLY non-operational military news: military budgets, appointments, promotions, parades, ceremonies, arms deals, defense diplomacy, and similar administrative/political topics. An operational military statement about combat power, deterrence, or threat response is war_conflict, NOT politics.
   - If it is only a civilian transport/aviation/maritime accident with no security clue, choose social.
   - Explosions rule: an explosion is war_conflict ONLY if it is a deliberate attack (bombing, shelling, strike, demolition) OR involves military ordnance/weapons. An explosion that results from a civilian fire, industrial accident, gas leak, fuel depot, or other non-military cause is social, even if the country is a conflict zone. The location (Afghanistan, Syria, Iraq) is irrelevant on its own — the CAUSE of the explosion decides.
7. Sports rule:
   - If the main entity is a sports organization, athlete, team, federation, FIFA, or sports official, choose sports, even if the news is about corruption, investigation, dismissal, or controversy.
8. Vague slogans & Newspaper teasers rule:
   - Do NOT classify vague slogans, metaphors, or poetic phrases as politics unless they explicitly mention government, elections, or officials. (e.g., "ما کف میدان ایستاده‌ایم" -> social).
   - If the text is a newspaper table of contents, magazine teaser, or a list of article titles (e.g., "Read in today's newspaper"), classify it based on the dominant theme. If it mixes religion, culture, and general topics, prefer culture_art or social. Do not let a single word like "commanders" override the whole context to politics.

CATEGORY DEFINITIONS:
- war_conflict: war, armed conflict, military attack, bombing, missile/drone strikes, invasion, ceasefire, armed clashes, naval/maritime security incidents, ship seizures, controlled explosions of munitions, unexploded ordnance, threats or official statements about attacks, AND official armed-forces communiqués about combat readiness, deterrence, defense/offense doctrine, interception, air defense, electronic/cyber warfare, or counter-threat capability.
- advertisement: promotion or selling of a product/service, discounts, registration calls, contact us, purchase links or phone numbers.
- politics: government, presidency, parliament, elections, diplomacy, sanctions talks, officials, political corruption, non-combat military news such as budget, appointments, parades, arms deals.
- economy: markets, inflation, currency, gold, banking, trade, prices, oil, fishermen's livelihood, trade routes, and the market effect of sanctions (price changes, supply disruptions, trade volume shifts).
- social: accidents, transport disruptions, aviation/airport/flight/maritime accidents without military cause, health, education, ordinary crime, environment, weather, urban issues, citizens' situations, slogans, social campaigns.
- sports: matches, tournaments, athletes, teams, sports federations, FIFA, sports officials, sports corruption, transfers, medals.
- culture_art: cinema, music, art, religion, tourism, ceremonies, mourning, funerals, books, literature, newspaper cultural sections.
- science_tech: AI, internet, space, gadgets, scientific research.

EXAMPLES:
Text: قیمت دلار امروز کاهش یافت و طلا ارزان شد
Answer: economy

Text: حرکت فوق‌العاده و گل زیبای امباپه به مراکش را از نمایی زیبا ببینید
Answer: sports

Text: درگیری مسلحانه در مرز دو کشور همسایه شدت گرفت
Answer: war_conflict

Text: مقام آمریکایی درباره حملات هوایی اخیر به مواضع نظامی اظهار نظر کرد
Answer: war_conflict

Text: وزیر دفاع از افزایش بودجه نظامی سال آینده خبر داد
Answer: politics

Text: مراسم تشییع و عزاداری در حرم برگزار شد
Answer: culture_art

Text: بهترین دوره آموزش زبان انگلیسی؛ برای ثبت‌نام با شماره زیر تماس بگیرید
Answer: advertisement

Text: سارقان مسلح بانک پس از تعقیب پلیس دستگیر شدند
Answer: social

Text: شرکت فناوری مدل جدید هوش مصنوعی خود را معرفی کرد
Answer: science_tech

Text: اختلال در فرود هواپیماها در فرودگاه بین‌المللی جده؛ علت نامشخص
Answer: war_conflict

Text: افشای فساد جدید از رییس فیفا ble.ir/join/GbhWkK5T6z
Answer: sports

Text: سازمان عملیات تجارت دریایی انگلیس از وقوع حادثه در ۱۸ مایل دریایی در شرق خصب در سلطان‌نشین عمان خبر داد
Answer: war_conflict

Text: خبرنگار آخرین خبر در نشست خبری رئیس‌جمهور پرسید و رئیس‌جمهور پاسخ داد
Answer: politics

Text: انفجار کنترل‌شدهٔ مهمات عمل‌نکردهٔ دشمن در سیریک انجام می‌شود
Answer: war_conflict

Text: منابع خبری از یک حادثه امنیتی جدید در دریای سرخ گزارش می‌دهند
Answer: war_conflict

Text: یک پیام خاص از میدان به خیابان؛ ما کف میدان ایستاده‌ایم!
Answer: social

Text: در روزنامه خراسان سه‌شنبه ۲۰ مرداد ماه ۱۴۰۵ بخوانید: ماموریت‌های جدید فرماندهان، حرم، نسبت بی‌نهایت، کریمانه زیستن در هیاهوی شهر
Answer: culture_art

Text: وضعیت ایرانی‌ها در تنگه هرمز
Answer: social

Text: توقیف یک کشتی خارجی در تنگه هرمز توسط نیروی دریایی سپاه
Answer: war_conflict

Text: انفجارهای مهیب در پی آتش‌سوزی گسترده در افغانستان؛ وقوع حریق در یک فروشگاه عرضه گاز و سوخت در شهر جاغوری، منجر به سلسله انفجارهای پیاپی شد.
Answer: social

Text: سخنگوی دولت در نشست خبری هفتگی درباره سیاست‌های اقتصادی دولت توضیح داد
Answer: politics

Text: مسعود پزشکیان جهت ایراد سخنرانی وارد ساختمان سازمان ملل متحد شد
Answer: politics

Text: رئیس‌جمهور برای حضور در مجمع عمومی سازمان ملل وارد نیویورک شد
Answer: politics

CRITICAL:
Output ONLY one lowercase category name. No explanation, no punctuation, no extra words.
"""


def _clean_text_for_classification(text: str) -> str:
    text = URL_PATTERN.sub(" ", text)
    text = MENTION_PATTERN.sub(" ", text)
    text = text.replace("|", " ")
    text = MARKDOWN_PATTERN.sub(" ", text)
    text = EMOJI_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def _request_category(cleaned_text: str) -> str | None:
    """یک فراخوانی مدل؛ None یعنی پاسخ خالی بود (نه خطای شبکه)."""
    response = open_ai_client.chat.completions.create(
        model=OPEN_AI_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Text: {cleaned_text}\nAnswer:"},
        ],
        temperature=0.0,
    )

    if not response.choices:
        return None

    content = response.choices[0].message.content
    return content.strip() if content else None


def classify_news(news_text: str) -> NewsCategory | None:
    cleaned_text = _clean_text_for_classification(news_text.strip())

    if not cleaned_text:
        return None

    try:
        # گیتوی گاهی پاسخ ۲۰۰ اما بدون choices برمی‌گرداند؛ چند بار تلاش کن
        # تا یک اجرا با یک پاسخ خالی وسط کار نخوابد.
        for attempt in range(MAX_EMPTY_RESPONSE_RETRIES + 1):
            raw_output = _request_category(cleaned_text)
            if raw_output is not None:
                return _parse_category(raw_output)
            if attempt < MAX_EMPTY_RESPONSE_RETRIES:
                print(f"⚠ پاسخ خالی از مدل؛ تلاش دوباره ({attempt + 1}/{MAX_EMPTY_RESPONSE_RETRIES})")
                time.sleep(1)

        raise RuntimeError("مدل پس از چند تلاش پاسخ خالی برگرداند")

    except Exception as e:
        print(f"خطا در ارتباط با مدل: {e}")
        raise e


def _parse_category(raw_output: str) -> NewsCategory:
    """خروجی خام مدل را به Enum تبدیل می‌کند (با تحمل خطای مدل‌های ضعیف)."""
    # تطابق دقیق
    for category in NewsCategory:
        if category.value == raw_output:
            return category

    # تطابق جزئی (مدل‌های ضعیف گاهی کلمه اضافه می‌گویند)
    for category in NewsCategory:
        if category == NewsCategory.UNKNOWN:
            continue
        if category.value in raw_output:
            return category

    return NewsCategory.UNKNOWN


# تست
if __name__ == "__main__":
    sample_news = [
        "️\nتقویم امروز جمعه ۱۶ مرداد ۱۴۰۵",
        "یک پیام خاص از میدان به خیابان؛ ما کف میدان ایستاده‌ایم!",
        "تقویم امروز شنبه ۱۷ مرداد ۱۴۰۵",
        "صفحه نخست روزنامه‌های ‌شنبه  ۱۷ مرداد ۱۴۰۵",
        "اختلال در فرود هواپیماها در فرودگاه بین‌المللی جده\nچندین فروند هواپیمای مسافربری در فرودگاه بین‌المللی جده در عربستان سعودی با مشکل فرود مواجه شده‌اند.\nبر اساس گزارش رسانه‌های عربی، تعدادی از هواپیماهای غیرنظامی قادر به فرود در فرودگاه بین‌المللی جده نیستند و علت این اختلال تاکنون مشخص نشده است.",
        "حسین اژدهایی، خبرنگار معروف هرمزگانی از شکل‌گیری وانتخاب لحن خاصش در گزارشاتش می‌گوید",
        "افشای فساد جدید از رییس فیفا/پای یک زن در میان است\nble.ir/join/GbhWkK5T6z\nble.ir/join/GbhWkK5T6z\nble.ir/join/GbhWkK5T6z",
        "وقوع حادثه دریایی در سواحل عمان\nسازمان عملیات تجارت دریایی انگلیس از وقوع حادثه در ۱۸ مایل دریایی در شرق خصب در سلطان نشین عمان خبر داد.",
        "️\nخبرنگار \"آخرین خبر\" در نشست خبری امروز با رئیس جمهور چه پرسید و رئیس جمهور چه جوابی به آن داد؟\n️سوال جنجالی و پاسخ صریح رئیس جمهور؛ وقتی می‌جنگیم کمبود هم پیدا می‌کنیم\n@akharinkhabar\n|",
        "انفجار کنترل‌شدهٔ مهمات در سیریک\nفرمانداری سیریک: انفجار کنترل‌شدهٔ مهمات عمل‌نکردهٔ دشمن امروز در بندرکوهستک انجام می‌شود؛ احتمال شنیدن صدای انفجار ناشی‌از این عملیات وجود دارد.",
        "️\nدر روزنامه خراسان سه‌شنبه ۲۰ مرداد ماه ۱۴۰۵ بخوانید\n️ماموریت‌های جدید فرماندهان\n️حرم، نسبت بی‌نهایت\n️کریمانه زیستن در هیاهوی شهر",
        "منابع خبری از یک حادثه امنیتی جدید در دریای سرخ گزارش می دهند/ هنوز ماهیت این حادثه مشخص نیست",
        "وضعیت ایرانی‌ها در تنگه هرمز",
    ]

    for news in sample_news:
        category = classify_news(news)
        print(f"📰 {news}\n   ➜ Category: {category.value}\n")
