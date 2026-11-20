from types import SimpleNamespace

import pytest

import news_summarizer
from news_summarizer import _looks_persian, summarize_news_posts, summarize_single_post
from model import NewsPost
from open_ai_client_provider import ModelAnswer


def _answer(text, finish_reason="stop"):
    return ModelAnswer(text, finish_reason)

# پاسخ واقعی که یک backend ضعیف برای یک پست فارسی برگرداند و مستقیم به کانال رفت.
CHINESE_REFUSAL = "关于这个问题，我没有相关信息，您可以尝试问我其它问题，我会尽力为您解答~"

PERSIAN_SUMMARY = (
    "سخنگوی سپاه اعلام کرد که رئیس‌جمهور پیام اقتدار ملت ایران را در قلب نظام استکبار بازتولید کرد."
)


def test_empty_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky(_text, _media_kind=None, _published_ms=None):
        calls["n"] += 1
        return _answer(None, None) if calls["n"] < 3 else _answer(PERSIAN_SUMMARY)

    monkeypatch.setattr(news_summarizer, "_request_summary", flaky)

    assert summarize_news_posts("یک خبر برای خلاصه‌سازی") == PERSIAN_SUMMARY
    assert calls["n"] == 3


def test_persistent_empty_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_empty(_text, _media_kind=None, _published_ms=None):
        calls["n"] += 1
        return _answer(None, None)

    monkeypatch.setattr(news_summarizer, "_request_summary", always_empty)

    with pytest.raises(RuntimeError):
        summarize_news_posts("یک خبر برای خلاصه‌سازی")

    assert calls["n"] == news_summarizer.MAX_BAD_RESPONSE_RETRIES + 1


def test_non_persian_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def off_language(_text, _media_kind=None, _published_ms=None):
        calls["n"] += 1
        return _answer(CHINESE_REFUSAL) if calls["n"] < 3 else _answer(PERSIAN_SUMMARY)

    monkeypatch.setattr(news_summarizer, "_request_summary", off_language)

    assert summarize_news_posts("یک خبر برای خلاصه‌سازی") == PERSIAN_SUMMARY
    assert calls["n"] == 3


def test_persistent_non_persian_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_chinese(_text, _media_kind=None, _published_ms=None):
        calls["n"] += 1
        return _answer(CHINESE_REFUSAL)

    monkeypatch.setattr(news_summarizer, "_request_summary", always_chinese)

    # اجرا می‌شکند و پست در news_posts.json ذخیره نمی‌شود، پس در اجرای بعدی دوباره تلاش می‌شود.
    with pytest.raises(RuntimeError):
        summarize_news_posts("یک خبر برای خلاصه‌سازی")

    assert calls["n"] == news_summarizer.MAX_BAD_RESPONSE_RETRIES + 1


def test_unusable_summary_is_logged_with_the_raw_output(monkeypatch, capsys):
    """پاسخ بی‌استفاده باید با متن خام خودش لاگ شود.

    تا ۲۵ سپتامبر ۲۰۲۶ فقط «پاسخ غیرفارسی از مدل» چاپ می‌شد و معلوم نبود مدل
    چه نوشته بود؛ حالا شکل خرابی از لاگ خوانده می‌شود.
    """
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    monkeypatch.setattr(
        news_summarizer,
        "_request_summary",
        lambda _text, _media_kind=None, _published_ms=None: _answer(CHINESE_REFUSAL, "length"),
    )

    with pytest.raises(RuntimeError) as excinfo:
        summarize_news_posts("یک خبر برای خلاصه‌سازی")

    output = capsys.readouterr().out
    assert "finish_reason=length" in output
    assert CHINESE_REFUSAL[:40] in output
    # همان توصیف در پیام استثنا هم می‌آید، چون لاگ نهایی از همان ساخته می‌شود.
    assert "finish_reason=length" in str(excinfo.value)


def test_looks_persian_rejects_other_scripts():
    assert not _looks_persian(CHINESE_REFUSAL)
    assert not _looks_persian("I don't have information about this question.")
    assert not _looks_persian("")


@pytest.mark.parametrize(
    "text",
    [
        # خلاصه‌های واقعی همین پست در بازتولید محلی
        "سخنگوی سپاه اعلام کرد که رئیس‌جمهور امروز در قلب نظام استکبار، پیام قدرت و عزت ملت ایران را بازتولید کرد.",
        "سخنگوی سپاه، سردار محبی، گفت رئیس‌جمهور پیام قدرت، غرور، عزت و امید ملت ایران را بازتولید کرد.",
        # نام لاتین داخل متن فارسی نباید خلاصه را رد کند
        "سخنگوی سپاه درباره بازی FIFA توضیح داد و گفت پیام اقتدار ملت ایران بازتولید شد.",
    ],
)
def test_looks_persian_accepts_persian_summaries(text):
    assert _looks_persian(text)


def test_blank_text_returns_none_without_calling_model(monkeypatch):
    def boom(_text, _published_ms=None):
        raise AssertionError("نباید برای متن خالی به مدل درخواست بزند")

    monkeypatch.setattr(news_summarizer, "_request_summary", boom)
    assert summarize_news_posts("   ") is None


class _RecordingCompletions:
    """کلاینت قلابی که پیام‌های فرستاده‌شده را نگه می‌دارد."""

    def __init__(self, content):
        self.content = content
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        choice = SimpleNamespace(
            message=SimpleNamespace(content=self.content), finish_reason="stop"
        )
        return SimpleNamespace(choices=[choice])


def _record_client(monkeypatch, module, content):
    fake = _RecordingCompletions(content)
    monkeypatch.setattr(
        module, "open_ai_client", SimpleNamespace(chat=SimpleNamespace(completions=fake))
    )
    return fake


def test_published_time_is_metadata_not_part_of_the_news(monkeypatch):
    fake = _record_client(monkeypatch, news_summarizer, PERSIAN_SUMMARY)

    summarize_news_posts("متن خبر", published_ms=1795098193219)

    system = fake.requests[0]["messages"][0]["content"]
    user = fake.requests[0]["messages"][1]["content"]
    assert "METADATA" in system
    assert "۲۸ آبان ۱۴۰۵" in system
    # تاریخ نباید داخل متن خبر برود؛ وگرنه مدل آن را جزو خبر می‌خواند.
    assert "۱۴۰۵" not in user
    assert user.strip() == "متن خبر"


def test_without_published_time_the_prompt_is_unchanged(monkeypatch):
    fake = _record_client(monkeypatch, news_summarizer, PERSIAN_SUMMARY)

    summarize_news_posts("متن خبر")

    system = fake.requests[0]["messages"][0]["content"]
    assert system == news_summarizer.SYSTEM_PROMPT


def test_single_post_sends_its_own_publication_date(monkeypatch):
    """مسیر واقعی ارسال باید تاریخ همان پست را بفرستد، نه تاریخ دیگری.

    بدون این تست، حذف post.date_ms از summarize_single_post هیچ تستی را قرمز
    نمی‌کرد و تاریخ به خلاصه‌ساز نمی‌رسید.
    """
    fake = _record_client(monkeypatch, news_summarizer, PERSIAN_SUMMARY)

    post = NewsPost(sid="-42-1795098193219", text="خ" * 300)
    summarize_single_post(post)

    system = fake.requests[0]["messages"][0]["content"]
    user = fake.requests[0]["messages"][1]["content"]
    assert "۲۸ آبان ۱۴۰۵" in system
    assert "۱۴۰۵" not in user
