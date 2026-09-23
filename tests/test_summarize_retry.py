import pytest

import news_summarizer
from news_summarizer import summarize_news_posts


def test_empty_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky(_text):
        calls["n"] += 1
        return None if calls["n"] < 3 else "خلاصهٔ خبر"

    monkeypatch.setattr(news_summarizer, "_request_summary", flaky)

    assert summarize_news_posts("یک خبر برای خلاصه‌سازی") == "خلاصهٔ خبر"
    assert calls["n"] == 3


def test_persistent_empty_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_summarizer.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_empty(_text):
        calls["n"] += 1
        return None

    monkeypatch.setattr(news_summarizer, "_request_summary", always_empty)

    with pytest.raises(RuntimeError):
        summarize_news_posts("یک خبر برای خلاصه‌سازی")

    assert calls["n"] == news_summarizer.MAX_EMPTY_RESPONSE_RETRIES + 1


def test_blank_text_returns_none_without_calling_model(monkeypatch):
    def boom(_text):
        raise AssertionError("نباید برای متن خالی به مدل درخواست بزند")

    monkeypatch.setattr(news_summarizer, "_request_summary", boom)
    assert summarize_news_posts("   ") is None
