from config import OPEN_AI_MODEL_NAME
from model import NewsCategory, NewsPost
from open_ai_client_provider import open_ai_client

BALE_POST_LINK_TEMPLATE = "https://ble.ir/akharinkhabar/{post_id}"

SYSTEM_PROMPT = """تو یک خلاصه‌ساز حرفه‌ای اخبار فارسی هستی.
متنی که کاربر می‌فرسته شامل چندین خبر است که پشت سر هم قرار دارند.

وظیفه تو:
- هر خبر را در یک پاراگراف خلاصه کن و اول هر پاراگراف ایموجی 🔷 با فاصله بذار
- هر خلاصه تا حد ممکن کوتاه باشه و به نکات مهم بسنده کن
- فقط در صورتی که منبع یا گوینده در متن خبر مشخص هست، آن را ذکر کن. فقط اگر مقام گوینده در متن خبر مشخص هست آن را هم اضافه کن (مثلاً: «رویترز: ...» یا «جامه‌گیر، عضو هیئت‌ مدیره تعاونی صیادان پشت‌شهر بندرعباس: ...»)
- اعداد، تاریخ‌ها، اسامی کلیدی و اطلاعات مهم را نگه دار، بقیه جزئیات را حذف کن
- خبرهای تکراری را در یک مورد ادغام کن (ولی این باعث نشه که خبرهایی به اشتباه نادیده گرفته بشن)
- هیچ توضیح یا مقدمه اضافه‌ای نده؛ مستقیم لیست را شروع کن"""


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
    summary += "\n\n\n"
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
