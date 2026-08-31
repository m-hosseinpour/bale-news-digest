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

CRITICAL RULE FOR QUESTION-STYLE NEWS:
If the input text is a question (e.g., "چرا ایران به اردن حمله کرد؟", "آیا توافق خواهد شد؟", "چه کسی مسئول است؟"):
- NEVER answer the question.
- NEVER generate explanations, analysis, reasons, or context that are not explicitly written in the input text.
- ONLY summarize or rephrase the question itself as a news headline.
- If the question is the entire news content, output ONLY the rephrased question (with 🔷 at the beginning).
- Example input: "چرا ایران در حملات دیشب اردن را هدف قرار داد؟"
- Correct output: "🔷 بررسی دلایل هدف قرار دادن اردن توسط ایران در حملات دیشب."
- INCORRECT output (DO NOT DO THIS): "🔷 ایران به اردن حمله کرد به دلیل حمایت اردن از اسرائیل در جنگ غزه..." (this adds information not in the input).

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
# and are passed through to the final message without an LLM call.
SHORT_TEXT_THRESHOLD = 150


def _format_short(text: str) -> str:
    """Wrap a short post text in the same 🔷 format the LLM produces."""
    return f"🔷 {text.strip()}"


def summarize_and_post_links(news_batch: list[NewsPost]):
    # Split the batch into short texts (used verbatim) and long texts (sent to LLM),
    # while remembering each post's original index so we can restore order.
    short_summaries: dict[int, str] = {}
    long_posts: list[tuple[int, NewsPost]] = []

    for idx, p in enumerate(news_batch):
        if len(p.text) < SHORT_TEXT_THRESHOLD:
            short_summaries[idx] = _format_short(p.text)
        else:
            long_posts.append((idx, p))

    llm_summary: str | None = None
    if long_posts:
        long_texts = [p.text for _, p in long_posts]
        concat_text = "\n\n***\n\n".join(long_texts)
        llm_summary = summarize_news_posts(concat_text) or ""

        # If the LLM returned one block per long post, re-attach them at the
        # right positions. Otherwise (e.g. LLM merged posts) prepend the
        # whole LLM output before the short summaries.
        llm_blocks = [b for b in llm_summary.split("\n\n") if b.strip()]
        if len(llm_blocks) == len(long_posts):
            for (idx, _), block in zip(long_posts, llm_blocks):
                short_summaries[idx] = block.strip()
            final_summaries = [short_summaries[i] for i in sorted(short_summaries)]
            summary = "\n\n".join(final_summaries)
        else:
            short_blocks = [short_summaries[i] for i in sorted(short_summaries)]
            if short_blocks:
                summary = llm_summary.strip() + "\n\n" + "\n\n".join(short_blocks)
            else:
                summary = llm_summary.strip()
    else:
        # No long posts — every summary comes from short texts.
        summary = "\n\n".join(short_summaries[i] for i in sorted(short_summaries))

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
