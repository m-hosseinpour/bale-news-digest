import pytest

import news_summarizer
from news_summarizer import _looks_persian, summarize_news_posts
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

    def flaky(_text, _media_kind=None):
        calls["n"] += 1
        return _answer(None, None) if calls["n"] < 3 else _answer(PERSIAN_SUMMARY)

    monkeypatch.setattr(news_summarizer, "_request_summary", flaky)

    assert summarize_news_posts("یک خبر برای خلاصه‌سازی") == PERSIAN_SUMMARY
    assert calls["n"] == 3


def test_persistent_empty_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_empty(_text, _media_kind=None):
        calls["n"] += 1
        return _answer(None, None)

    monkeypatch.setattr(news_summarizer, "_request_summary", always_empty)

    with pytest.raises(RuntimeError):
        summarize_news_posts("یک خبر برای خلاصه‌سازی")

    assert calls["n"] == news_summarizer.MAX_BAD_RESPONSE_RETRIES + 1


def test_non_persian_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def off_language(_text, _media_kind=None):
        calls["n"] += 1
        return _answer(CHINESE_REFUSAL) if calls["n"] < 3 else _answer(PERSIAN_SUMMARY)

    monkeypatch.setattr(news_summarizer, "_request_summary", off_language)

    assert summarize_news_posts("یک خبر برای خلاصه‌سازی") == PERSIAN_SUMMARY
    assert calls["n"] == 3


def test_persistent_non_persian_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_chinese(_text, _media_kind=None):
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
        lambda _text, _media_kind=None: _answer(CHINESE_REFUSAL, "length"),
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
    def boom(_text):
        raise AssertionError("نباید برای متن خالی به مدل درخواست بزند")

    monkeypatch.setattr(news_summarizer, "_request_summary", boom)
    assert summarize_news_posts("   ") is None
