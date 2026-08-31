from config import OPEN_AI_MODEL_NAME
from model import NewsCategory, NewsPost
from open_ai_client_provider import open_ai_client

BALE_POST_LINK_TEMPLATE = "https://ble.ir/akharinkhabar/{post_id}"

SYSTEM_PROMPT = """You are a professional Persian news summarizer.
The input text contains a single news item.

CRITICAL OUTPUT LANGUAGE RULE:
- The summary output MUST ALWAYS be written in fluent, natural Persian (Farsi).
- Never write the summary content in English or any other language.
- Only the formatting instructions and labels are in English; the actual news summary must be in Persian.

YOUR TASK:
- Write the news item as a concise but complete and understandable paragraph.
- The summary should typically be 1 to 2 sentences; maximum 3 sentences only if the news contains multiple very important points.
- Avoid long writing, repetition, unnecessary background, and unnecessary quotes.
- Avoid over-shortening; the summary must still clarify what happened, to whom/where, and why it matters.
- Focus only on key points.
- Mention the source or speaker only if explicitly stated in the text, along with their title/position, briefly (e.g., "Reuters: ..." or "X, board member: ...").
- Stay strictly faithful to the input text; NEVER add information, names, or positions that are not in the text.
- Preserve all numbers, dates, locations, and key names; remove only low-importance details.
- Start the output directly with the summarized Persian text, without any emoji, label, introduction, or extra explanation.
- NEVER write phrases like "خلاصه خبر", "Summary", or similar labels.

CRITICAL RULE FOR QUESTION-STYLE NEWS:
If the input text is a question (e.g., "چرا ایران به اردن حمله کرد؟", "آیا توافق خواهد شد؟", "چه کسی مسئول است؟"):
- NEVER answer the question.
- NEVER generate explanations, analysis, reasons, or context that are not explicitly written in the input text.
- ONLY summarize or rephrase the question itself as a news headline.
- Example input: "چرا ایران در حملات دیشب اردن را هدف قرار داد؟"
- Correct output: "بررسی دلایل هدف قرار دادن اردن توسط ایران در حملات دیشب."
- INCORRECT output (DO NOT DO THIS): "ایران به اردن حمله کرد به دلیل حمایت اردن از اسرائیل در جنگ غزه..." (this adds information not in the input).

CRITICAL RULE FOR NON-SUMMARIZABLE TEXTS:
If the input text cannot be summarized as news (e.g., it is just a description of a photo or video, has no clear news content, is a general question, or lacks a news structure):
- NEVER write phrases like "this text is not news", "please send a news text", "this text cannot be summarized", or similar error/explanation messages.
- Instead, return the EXACT original input text unchanged.
- This is an absolute rule; never output an error message, explanation, or request to send new text.
"""


def summarize_news_posts(news_text: str) -> str | None:
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


# Texts shorter than this many characters are considered already-summarized
# and are passed through without an LLM call.
SHORT_TEXT_THRESHOLD = 150


def summarize_single_post(post: NewsPost) -> str:
    """Return the summary text for a single post. Short posts skip the LLM."""
    text = post.text.strip()
    if len(text) < SHORT_TEXT_THRESHOLD:
        return text
    return summarize_news_posts(text) or text


def _post_link(post: NewsPost) -> str:
    separator_index = post.sid.index("-", 1)
    post_id = post.sid[:separator_index] + "/" + post.sid[separator_index + 1:]
    return BALE_POST_LINK_TEMPLATE.format(post_id=post_id)


def compose_message(post: NewsPost, summary: str) -> str:
    return f"{summary}\n\nلینک خبر مرجع:\n{_post_link(post)}"


# تست
if __name__ == "__main__":
    sample_news_text = (
        "چرا ایران در حملات دیشب اردن را هدف قرار داد؟\n"
        "آیا توافق هسته‌ای احیا خواهد شد؟\n"
        "چه کسی مسئول انفجار در بیروت است؟\n"
        "بانک مرکزی نرخ سود سپرده‌ها را افزایش داد\n"
        "پرسپولیس در دربی تهران استقلال را شکست داد\n"
        "شرکت اپل از آیفون جدید خود رونمایی کرد\n"
        "وزیر امور خارجه با همتای روس خود دیدار کرد\n"
        "آلودگی هوای تهران مدارس را تعطیل کرد"
    )
    print(summarize_news_posts(sample_news_text))
