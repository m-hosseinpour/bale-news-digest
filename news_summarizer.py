from config import OPEN_AI_MODEL_NAME
from model import NewsCategory, NewsPost
from open_ai_client_provider import open_ai_client

BALE_POST_LINK_TEMPLATE = "https://ble.ir/akharinkhabar/{post_id}"

SYSTEM_PROMPT = """تو یک خلاصه‌ساز حرفه‌ای اخبار فارسی هستی.
متنی که کاربر می‌فرسته شامل چندین خبر است که پشت سر هم قرار دارند.

وظیفه تو:
- هر خبر (یا اخبار ادغام‌شده) را در یک پاراگرافِ کوتاه بنویس و اول آن ایموجی 🔷 بذار.
- بین هر دو خلاصه دقیقاً یک خط خالی قرار بده.
- قبل از اولین خلاصه و بعد از آخرین خلاصه خط خالی اضافی نگذار.
- اگر فقط یک خبر وجود داشت، همان را بدون خط خالی اضافه خروجی بده.
- فقط به نکات مهم اکتفا کن.
- منبع یا گوینده را فقط در صورت ذکر شدن در متن، همراه با سمتش بنویس (مثلاً: «رویترز: ...» یا «فلانی، عضو هیئت‌مدیره ...: ...»).
- فقط به متن ورودی وفادار باش و از اضافه کردن اطلاعات، نام‌ها یا مقام‌های خارج از متن به‌شدت خودداری کن.
- اعداد، تاریخ‌ها، مکان‌ها و اسامی کلیدی را حتماً حفظ کن و بقیه جزئیات را حذف کن.
- اخبار کاملاً تکراری را در یک مورد ادغام کن (مراقب باش اخبارِ متفاوت به اشتباه نادیده گرفته نشوند).
- بدون هیچ‌گونه مقدمه، مؤخره یا توضیح اضافی، مستقیماً لیست را شروع کن.

فرمت خروجی باید دقیقاً به این شکل باشد:
🔷 خلاصه خبر اول

🔷 خلاصه خبر دوم

🔷 خلاصه خبر سوم
"""

def summarize_news_posts(news_text: str) -> NewsCategory | None:
    news_text_strip = news_text.strip()
    if not news_text_strip:
        return None

    try:
        response = open_ai_client.chat.completions.create(
            model=OPEN_AI_MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": news_text},
            ],
            temperature=0.3,  # کمتر = دقیق‌تر و خلاصه‌تر
            timeout=300,  # تایم‌اوت برای CPU ضعیف
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"خطا در ارتباط با مدل: {e}")
        raise e


def summarize_and_post_links(news_batch: list[NewsPost]):
    concat_text = "\n\n***\n\n".join([p.text for p in news_batch])
    summary = summarize_news_posts(concat_text)
    summary += "\n\n\nلینک خبرهای مرجع:\n"
    for p in news_batch:
        separator_index = p.sid.index("-", 1)
        post_id = p.sid[:separator_index] + "/" + p.sid[separator_index + 1:]
        summary += BALE_POST_LINK_TEMPLATE.format(post_id=post_id) + "\n"

    print('=' * 50 + ' SUMMARY-TO-SEND ' + '=' * 50)
    print(summary)
    return summary


# تست
if __name__ == "__main__":
    sample_news_text = ("بانک مرکزی نرخ سود سپرده‌ها را افزایش داد\n"
                        "پرسپولیس در دربی تهران استقلال را شکست داد\n"
                        "شرکت اپل از آیفون جدید خود رونمایی کرد\n"
                        "وزیر امور خارجه با همتای روس خود دیدار کرد\n"
                        "آلودگی هوای تهران مدارس را تعطیل کرد")
    print(summarize_news_posts(sample_news_text))
