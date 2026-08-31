from config import OPEN_AI_MODEL_NAME
from model import NewsCategory, NewsPost
from open_ai_client_provider import open_ai_client

BALE_POST_LINK_TEMPLATE = "https://ble.ir/akharinkhabar/{post_id}"

SYSTEM_PROMPT = """You are a professional Persian news summarizer.
The input text contains multiple news items placed consecutively.

CRITICAL OUTPUT LANGUAGE RULE:
- The summary output MUST ALWAYS be written in fluent, natural Persian (Farsi).
- Never write the summary content in English or any other language.
- Only the formatting instructions and labels are in English; the actual news summaries must be in Persian.

YOUR TASK:
- Write each news item (or merged news items) as a concise but complete and understandable paragraph.
- Each summary should typically be 1 to 2 sentences; maximum 3 sentences only if the news contains multiple very important points.
- Avoid long writing, repetition, unnecessary background, and unnecessary quotes.
- Avoid over-shortening; the summary must still clarify what happened, to whom/where, and why it matters.
- Start each summary with the 🔷 emoji.
- Place exactly one blank line between each summary.
- Do NOT add extra blank lines before the first summary or after the last summary.
- If there is only one news item, output it without extra blank lines.
- Focus only on key points.
- Mention the source or speaker only if explicitly stated in the text, along with their title/position, briefly (e.g., "Reuters: ..." or "X, board member: ...").
- Stay strictly faithful to the input text; NEVER add information, names, or positions that are not in the text.
- Preserve all numbers, dates, locations, and key names; remove only low-importance details.
- Merge completely duplicate news into a single item (be careful NOT to mistakenly ignore different news).
- Start the list of summaries directly without any introduction, conclusion, or extra explanation.
- NEVER write phrases like "خلاصه خبر اول", "خبر دوم", "Summary 1", "News 2", or similar labels. Only place the summarized Persian text after the 🔷 emoji.

CRITICAL RULE FOR NON-SUMMARIZABLE TEXTS:
If the input text cannot be summarized as news (e.g., it is just a description of a photo or video, has no clear news content, is a general question, or lacks a news structure):
- NEVER write phrases like "this text is not a list of news", "please send a news text", "this text cannot be summarized", or similar error/explanation messages.
- Instead, return the EXACT original input text unchanged, prefixed with 🔷 at the beginning.
- This is an absolute rule; never output an error message, explanation, or request to send new text.

OUTPUT FORMAT must be EXACTLY like this:
🔷 [خلاصهٔ خبر اول به فارسی]

🔷 [خلاصهٔ خبر دوم به فارسی]

🔷 [خلاصهٔ خبر سوم به فارسی]
"""


def summarize_news_posts(news_text: str) -> str | None:
    news_text_strip = news_text.strip()
    if not news_text_strip:
        return None

    if len(news_text_strip) < 150:
        return news_text_strip

    try:
        response = open_ai_client.chat.completions.create(
            model=OPEN_AI_MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": news_text},
            ],
            temperature=0.0,
            timeout=300,
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise RuntimeError("جواب هوش مصنوعی خالی بود")
        return content
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
