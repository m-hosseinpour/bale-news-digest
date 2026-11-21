from typing import NamedTuple

from openai import OpenAI

from config import OPEN_AI_BASE_URL, OPEN_AI_API_KEY

# OpenCode Go (opencode.ai/inference/go) از کلاینتی که صدایش می‌زند می‌خواهد با
# نام خودش معرفی شود و یک شناسهٔ ثابت نشست بفرستد تا مسیریابی و کش پرامپت
# پایدار بماند. providerهای دیگر به این دو هدر نیازی ندارند.
# شناسه عمداً برای همهٔ پست‌ها یکی است، نه یکتا برای هر پست: پرامپت سیستمی
# تکرارشونده است و همین باعث می‌شود در کش بماند.
LLM_USER_AGENT = "bale-news-digest/1.0"
LLM_SESSION_ID = "ses_bale_news_digest"

open_ai_client = OpenAI(
    base_url=OPEN_AI_BASE_URL,
    api_key=OPEN_AI_API_KEY,
    default_headers={
        "User-Agent": LLM_USER_AGENT,
        "x-opencode-session": LLM_SESSION_ID,
    },
)


class ModelAnswer(NamedTuple):
    """پاسخ یک فراخوانی مدل: متن و علت پایان‌یافتنش."""

    text: str | None
    finish_reason: str | None


# چقدر از پاسخ خام در لاگ بیاید. کافی است تا شکل خرابی معلوم شود
# (متن بلند خارج از نقش، بریدگی، پاسخ چینی) بدون آنکه لاگ را پر کند.
RAW_ANSWER_LOG_CHARS = 300


def describe_answer(answer: ModelAnswer | None) -> str:
    """پاسخ خام مدل را برای لاگ توصیف می‌کند.

    بدون این، شکست‌های «پاسخ بی‌استفاده» هیچ ردی از خودشان جا نمی‌گذاشتند و
    بعد از وقوع قابل تشخیص نبودند — مدل پاسخی داده بود که هیچ‌جا دیده نمی‌شد.
    """
    if answer is None:
        return "پاسخی نرسید"

    parts = [f"finish_reason={answer.finish_reason}"]
    if answer.text is None:
        parts.append("متن خالی")
    else:
        parts.append(f"پاسخ خام: {answer.text[:RAW_ANSWER_LOG_CHARS]!r}")
    return " | ".join(parts)
