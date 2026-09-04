import re

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
- Stay strictly faithful to the input text; NEVER add information, names, or positions that are not in the text.
- Preserve all numbers, dates, locations, and key names; remove only low-importance details.
- Start the output directly with the summarized Persian text, without any emoji, label, introduction, or extra explanation.
- NEVER write phrases like "خلاصه خبر", "Summary", or similar labels.

CRITICAL RULE FOR SPEAKERS, TITLES, POSITIONS, AND AFFILIATIONS:
- NEVER guess, infer, or invent a person's title, position, role, or organizational affiliation.
- If the input text mentions a person by name (e.g., "همتی") but does NOT state their title, position, or affiliation in the text itself, refer to them ONLY by that exact name — NEVER add "رئیس بانک مرکزی", "نماینده بانک مرکزی", "وزیر", "کارشناس", "خبرنگار", or any other descriptor.
- If the input text mentions a handle, channel name, or social-media username (with or without a leading "♦️" or other emoji), treat it ONLY as that handle — it is a person posting/tweeting, not a position holder. Do not turn handles into job titles based on real-world knowledge of those people.
- The same applies to organizations, parties, and countries mentioned in the text: copy them exactly as written, and NEVER add an affiliation, nationality, or category that is not in the text.
- If you are not 100% sure a title/position is written in the input text, OMIT it. Guessing based on who the person is in the real world is a hard error and must never happen.

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

# Match channel/user symbols like @akharingheimatt, @channel_name123
_SYMBOL_RE = re.compile(r"@[A-Za-z0-9_]+")
# Match bale channel links such as https://ble.ir/s/akharinkhabar or ble.ir/anything
_CHANNEL_LINK_RE = re.compile(r"https?://ble\.ir/\S+|ble\.ir/\S+", re.IGNORECASE)
# Match a single emoji (covers most common ranges, including ZWJ sequences)
_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF☀-➿⌀-⏿"
    r"‍️]+"
)


def _strip_symbols_and_channel_links(text: str) -> str:
    """Remove @symbols and ble.ir channel links from any position in the text."""
    text = _SYMBOL_RE.sub("", text)
    text = _CHANNEL_LINK_RE.sub("", text)
    return text


def _strip_edge_emojis(text: str) -> str:
    """Strip leading/trailing whitespace and emojis from both ends."""
    return _EMOJI_RE.sub("", text).strip()


def _clean_short_text(text: str) -> str:
    """Clean a short post: drop @symbols, channel links, and edge emojis.

    Empty lines are collapsed and leading/trailing whitespace is removed.
    Returns an empty string when no meaningful content remains.
    """
    cleaned = _strip_symbols_and_channel_links(text)
    # Drop lines that became blank (or contained only whitespace/symbols).
    kept_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = "\n".join(kept_lines)
    cleaned = _strip_edge_emojis(cleaned)
    return cleaned


def summarize_single_post(post: NewsPost) -> str:
    """Return the summary text for a single post. Short posts skip the LLM."""
    text = post.text.strip()
    if len(text) < SHORT_TEXT_THRESHOLD:
        return _clean_short_text(text)
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
