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

SYSTEM_PROMPT = """You are a professional Persian news summarizer. The input text contains a single news item.

OUTPUT LANGUAGE: the summary is ALWAYS fluent Persian — never English or any other language.

YOUR TASK:
- Write the news item as a compact paragraph — the shortest wording that still carries the news.
- Typically 1 to 2 sentences; a third only if the text carries several very important points.
- Keep the main fact and drop what the reader does not need in order to know what happened: enumerations, secondary details, background and context sentences, stage-setting phrases («در این خصوص», «در ادامه», «به گزارش …»).
- Cut every word that does not carry news: attribution verbs («گفت», «اعلام کرد», «تأکید کرد») when the fact stands on its own, empty intensifiers, a fact said twice in two wordings, and quotations unless the exact wording is the news. Keep an attribution or a qualifier only when it changes the fact.
- Stay strictly faithful to the input: never add information, names, or positions that are not in it.
- Start directly with the summary text — no emoji, no label like "خلاصه خبر" or "Summary", no introduction.

ABSOLUTE RULES:
1. THE OUTPUT IS ONLY THE NEWS. Never add a parenthetical, footnote, or closing sentence about the text, the summary, or your own writing — no "(این خلاصه بر اساس متن ارائه‌شده است)", no "شایان ذکر است" / "لازم به ذکر است", no mention of rules you applied or of what you cut, and no comment on typos or awkward wording in the input. Parentheses are allowed only when what is inside them is part of the news fact.
2. NEVER INVENT A TITLE, POSITION, ROLE, OR AFFILIATION. If the input names a person without stating their title, use the exact name alone — never add «وزیر», «رئیس …», «کارشناس», or an organization they are not given in the text. Copy organizations, parties, and countries exactly as written, adding no affiliation or category that is not in the text.
3. NEVER ANSWER A QUESTION. If the input is a question, restate the question itself as a news headline and add nothing beyond the text: "چرا ایران در حملات دیشب اردن را هدف قرار داد؟" → «بررسی دلایل هدف قرار دادن اردن توسط ایران در حملات دیشب.» Turning the question into a statement of fact, or supplying reasons or causes, is a hard error.
4. LINES THAT ARE NOT NEWS MUST NEVER APPEAR IN THE SUMMARY, as fact or as quotation: calls to interact (react, comment, share, forward, follow, vote, «نظرتون را اعلام کنید», «فالو کنید») and channel promotion (the channel's or admin's name, @handle, Telegram/Bale ID, «لینک کانال», join links, «اختصاصی ما», taglines, divider/hashtag decorations). A @handle or channel name that appears only in a promo or signature line is the channel's identity, not a news subject: omit it. Never report that the post asked for reactions.
5. NEVER MENTION AN ATTACHMENT. When the input notes a photo, video, audio, or file whose content you cannot see, write the summary as if the post were text-only: no «عکس», «تصویر», «فیلم», «ویدیو», «کلیپ», «صوت», «فایل», «ضمیمه», «منتشر شده», «در ادامه می‌بینید», and no phrase pointing the reader to a picture or clip.
6. IF NOTHING IS SUMMARIZABLE — no news content, only a description of a photo or video, or a general question — return the EXACT original input text unchanged. Never write an error message, an explanation, or a request to send a news text.
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
