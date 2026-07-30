from config import OPEN_AI_MODEL_NAME
from model import NewsCategory
from open_ai_client_provider import open_ai_client

# پرامپت سیستمی (بهینه برای مدل‌های ضعیف)
# نکته: برای مدل‌های ضعیف، پرامپت باید کوتاه، ساختارمند و با مثال باشد
SYSTEM_PROMPT = """You are a strict text classifier for Persian news. Output EXACTLY ONE word from this list and nothing else:
war_conflict, advertisement, politics, economy, social, sports, culture_art, science_tech, unknown

Follow the steps IN ORDER. Stop at the FIRST step that matches.

STEP 1 - war_conflict:
The MAIN topic is war or a military attack between countries or armed groups: missile/drone strikes, bombing, airstrikes, invasion, ceasefire, or official statements/denials ABOUT such attacks.
sample Keywords: جنگ، حمله موشکی، حمله هوایی، بمباران، پهپاد، آتش‌بس، تجاوز نظامی، انفجار
NOT war_conflict: ordinary crime like robbery or murder (سرقت مسلحانه، قتل) -> social. General military news like budget, appointments, parades, arms deals -> politics.

STEP 2 - advertisement:
The text promotes or sells a product/service: discounts, registration calls, "contact us", purchase links or phone numbers.
sample Keywords: فروش ویژه، تخفیف، ثبت‌نام کنید، تماس بگیرید، همین حالا خرید کنید، خرید تلفنی
NOT advertisement: news that only REPORTS prices or markets -> economy.

STEP 3 - choose the single best fit:
- politics: elections, parliament, government, diplomacy, sanctions talks, non-combat military news (انتخابات، مجلس، دولت، وزیر، دیپلماسی، مذاکرات)
- economy: markets, inflation, currency, gold, banking, trade, prices (تورم، قیمت، دلار، طلا، بورس، بانک)
- social: health, education, accidents, ordinary crime, environment, weather, urban issues (بیمارستان، تصادف، قتل، سرقت، آلودگی هوا، مدرسه)
- sports: matches, tournaments, athletes, teams, medals (فوتبال، مسابقه، مدال، قهرمانی، بازیکن، گل، جام جهانی، رختکن)
- culture_art: cinema, music, art, religion, tourism, ceremonies, mourning, funerals (سینما، موسیقی، گردشگری، حرم، عزاداری، تشییع، جشنواره)
- science_tech: AI, internet, space, gadgets, scientific research (هوش مصنوعی، اینترنت، فضا، گوشی، فناوری، تحقیقات علمی)
- unknown: empty, unclear, or none of the above.

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

CRITICAL RULES:
- Output ONLY the exact category name in English, lowercase.
- No explanations, punctuation, or extra words.
"""


def classify_news(news_text: str) -> NewsCategory | None:
    news_text_strip = news_text.strip()
    if not news_text_strip:
        return None

    try:
        response = open_ai_client.chat.completions.create(
            model=OPEN_AI_MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Text: {news_text_strip}\nAnswer:"},
            ],
            temperature=0.0,  # حداکثر قطعیت، مهم برای classification
        )

        raw_output = response.choices[0].message.content.strip()
        return _parse_category(raw_output)
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
        "بانک مرکزی نرخ سود سپرده‌ها را افزایش داد",
        "پرسپولیس در دربی تهران استقلال را شکست داد",
        "شرکت اپل از آیفون جدید خود رونمایی کرد",
        "وزیر امور خارجه با همتای روس خود دیدار کرد",
        "آلودگی هوای تهران مدارس را تعطیل کرد",
    ]

    for news in sample_news:
        category = classify_news(news)
        print(f"📰 {news}\n   ➜ دسته: {category.value}\n")
