import re
import time

from config import CHANNEL_SLUG, OPEN_AI_MODEL_NAME
from model import MediaKind, NewsPost
from open_ai_client_provider import open_ai_client

# تعداد تلاش مجدد وقتی پاسخ مدل قابل استفاده نیست: یا خالی است (گیتوی پاسخ
# ۲۰۰ اما بدون choices می‌دهد) یا غیرفارسی (بعضی backend‌ها از نقش خارج می‌شوند).
MAX_BAD_RESPONSE_RETRIES = 3

# گارد زبان خروجی. عمداً ساده و سهل‌گیر است: فقط پاسخ‌هایی را می‌گیرد که آشکارا
# به خط دیگری نوشته شده‌اند (چینی/انگلیسی/…) — نه عربی را از فارسی جدا می‌کند،
# چون سخت‌گیریِ بیشتر ریسک رد کردنِ خلاصهٔ درست را دارد.
_PERSIAN_LETTER_RE = re.compile(r"[\u0600-\u06FF]")
MIN_PERSIAN_LETTERS = 10


def _looks_persian(text: str) -> bool:
    """آیا خروجی مدل واقعاً فارسی است؟ (حداقل ۱۰ حرف فارسی و دست‌کم نیمی از حروف)"""
    persian = len(_PERSIAN_LETTER_RE.findall(text))
    letters = sum(1 for ch in text if ch.isalpha())
    return persian >= MIN_PERSIAN_LETTERS and persian * 2 >= letters


BALE_POST_LINK_TEMPLATE = f"https://ble.ir/{CHANNEL_SLUG}/{{post_id}}"

LINK_LABEL = "لینک خبر مرجع"

# برچسب ضمیمه که به مدل داده می‌شود (بدون فرستادن خود فایل یا لینکش).
MEDIA_KIND_LABELS = {
    MediaKind.PHOTO: "عکس",
    MediaKind.VIDEO: "ویدیو",
    MediaKind.AUDIO: "فایل صوتی",
    MediaKind.DOCUMENT: "فایل",
}

SYSTEM_PROMPT = """You are a professional Persian news summarizer.
The input text contains a single news item.

CRITICAL OUTPUT LANGUAGE RULE:
- The summary output MUST ALWAYS be written in fluent, natural Persian (Farsi).
- Never write the summary content in English or any other language.
- Only the formatting instructions and labels are in English; the actual news summary must be in Persian.

YOUR TASK:
- Write the news item as a concise and understandable paragraph.
- The summary should typically be 1 to 2 sentences; maximum 3 sentences only if the news contains multiple very important points.
- Avoid long writing, repetition, unnecessary background, and unnecessary quotes.
- Focus only on key points.
- Stay strictly faithful to the input text; NEVER add information, names, or positions that are not in the text.
- Start the output directly with the summarized Persian text, without any emoji, label, introduction, or extra explanation.
- NEVER write phrases like "خلاصه خبر", "Summary", or similar labels.

CRITICAL RULE AGAINST META-COMMENTARY:
- The output is the news itself. It is NEVER a comment about the summary, the input text, the source, or your own writing.
- NEVER append a parenthetical, bracket, footnote, or closing sentence that talks about the text or about your faithfulness to it. Forbidden examples: "(این خلاصه بر اساس متن ارائهشده است)", "(در متن اصلی ذکر شده است)", "(بر اساس متن)", "(بدون افزودن اطلاعات)".
- NEVER write phrases like "شایان ذکر است", "لازم به ذکر است", "قابل ذکر است" either — say the fact directly.
- Do NOT justify, explain, or reassure the reader that you stayed faithful to the input. Staying faithful is required, so it needs no mention; just write the summary.
- Parentheses are allowed ONLY when the parenthesized content is part of the news fact itself (e.g. the expanded form of an abbreviation that appears in the input).

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

CRITICAL RULE FOR CALLS TO ACTION AND CHANNEL PROMOTION:
The input text often contains lines that are NOT news content and must NEVER appear in the summary, neither as facts nor as quoted material:
- Invitations to interact: reacting, commenting, sharing/forwarding the post, following, voting, "نظرتون را اعلام کنید", "با لایک/ری‌اکشن ما را حمایت کنید", "فالو/جویین کنید", "Follow".
- Channel promotion: the channel's or admin's name, @handle, Telegram/Bale ID, "لینک کانال", join links, "اختصاصی ما", brand/tagline lines, and divider/hashtag decorations.
- These lines describe the poster's marketing, not an event. Ignore them completely and summarize only the actual news content of the text.
- Never mention that the post asked for reactions, comments, shares, or follows — such calls to action must not be reported in the summary either.
- Handle/@name appearing ONLY in a promotion or signature line is a channel identity, not a news subject: omit it. Copy a @handle into the summary ONLY if it is the source of a claim quoted in the news content itself.
- If after removing these lines no news content remains, return the EXACT original input text unchanged (see the non-summarizable rule).

CRITICAL RULE FOR NON-SUMMARIZABLE TEXTS:
If the input text cannot be summarized as news (e.g., it is just a description of a photo or video, has no clear news content, is a general question, or lacks a news structure):
- NEVER write phrases like "this text is not news", "please send a news text", "this text cannot be summarized", or similar error/explanation messages.
- Instead, return the EXACT original input text unchanged.
- This is an absolute rule; never output an error message, explanation, or request to send new text.

CRITICAL RULE FOR POSTS WITH AN ATTACHMENT:
Some posts carry an attachment (photo, video, audio, or file) whose content you cannot see. When the input notes such an attachment:
- NEVER mention the attachment in the summary: no words like "عکس", "تصویر", "فیلم", "ویدیو", "کلیپ", "صوت", "فایل", "ضمیمه", "منتشر شده", "در ادامه می‌بینید", nor any phrase pointing the reader to a picture or clip.
- The summary must read exactly like any other text-only news summary.
"""


def _media_hint(media_kind: MediaKind | None) -> str:
    """یادداشت متنی دربارهٔ وجود ضمیمه — خود فایل یا لینکش فرستاده نمی‌شود."""
    if media_kind is None:
        return ""
    label = MEDIA_KIND_LABELS.get(media_kind)
    if not label:
        return ""
    return f"\n\n[این خبر همراه یک {label} است.]"


def _request_summary(news_text: str, media_kind: MediaKind | None = None) -> str | None:
    """یک فراخوانی مدل؛ None یعنی پاسخ خالی بود (نه خطای شبکه)."""
    response = open_ai_client.chat.completions.create(
        model=OPEN_AI_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": news_text + _media_hint(media_kind)},
        ],
        temperature=0.0,
        timeout=300,
    )

    if not response.choices:
        return None

    content = response.choices[0].message.content
    return content.strip() if content else None


def summarize_news_posts(
    news_text: str, media_kind: MediaKind | None = None
) -> str | None:
    news_text_strip = news_text.strip()
    if not news_text_strip:
        return None

    try:
        # خروجی خالی یا غیرفارسی قابل استفاده نیست؛ چند بار تلاش کن تا یک اجرا
        # با یک پاسخ بد وسط کار نخوابد.
        for attempt in range(MAX_BAD_RESPONSE_RETRIES + 1):
            content = _request_summary(news_text, media_kind)
            if content is not None and _looks_persian(content):
                return content
            if attempt < MAX_BAD_RESPONSE_RETRIES:
                reason = "خالی" if content is None else "غیرفارسی"
                print(
                    f"⚠ پاسخ {reason} از مدل؛ تلاش دوباره "
                    f"({attempt + 1}/{MAX_BAD_RESPONSE_RETRIES})"
                )
                time.sleep(1)

        raise RuntimeError("پاسخ هوش مصنوعی پس از چند تلاش قابل استفاده نبود")

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
    return summarize_news_posts(text, post.media_kind) or text


def _post_link(post: NewsPost) -> str:
    separator_index = post.sid.index("-", 1)
    post_id = post.sid[:separator_index] + "/" + post.sid[separator_index + 1:]
    return BALE_POST_LINK_TEMPLATE.format(post_id=post_id)


def compose_message(post: NewsPost, summary: str) -> str:
    """متن خلاصه دست‌نخورده، و خط آخر یک لینک مارک‌داون."""
    return f"{summary}\n\n[{LINK_LABEL}]({_post_link(post)})"


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
