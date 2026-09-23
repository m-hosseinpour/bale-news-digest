import pytest

import news_classifier
from model import NewsCategory
from news_classifier import _clean_text_for_classification, classify_news


def test_strips_bold_markers_and_emoji():
    text = "*🔴مسعود پزشکیان جهت ایراد سخنرانی وارد ساختمان سازمان ملل متحد شد*"
    assert (
        _clean_text_for_classification(text)
        == "مسعود پزشکیان جهت ایراد سخنرانی وارد ساختمان سازمان ملل متحد شد"
    )


def test_strips_video_emoji_but_keeps_title():
    assert _clean_text_for_classification("*🎥 سقوط جنگنده انگلیسی*") == "سقوط جنگنده انگلیسی"


@pytest.mark.parametrize(
    "text",
    [
        "وضعیت ایرانی‌ها در تنگه هرمز",
        "اختلال در فرود در فرودگاه بین‌المللی جده",
        "انفجار کنترل‌شدهٔ مهمات عمل‌نکردهٔ دشمن",
    ],
)
def test_preserves_persian_letters_and_zwnj(text):
    # نیم‌فاصله (U+200C) بخشی از واژهٔ فارسی است و نباید حذف شود.
    assert _clean_text_for_classification(text) == text


def test_only_emoji_and_symbols_cleans_to_empty():
    assert _clean_text_for_classification("🔴🎥 *~` |") == ""


def test_emoji_only_text_classifies_as_none_without_calling_model(monkeypatch):
    def boom(_):
        raise AssertionError("نباید برای متن بدون محتوا به مدل درخواست بزند")

    monkeypatch.setattr(news_classifier, "_request_category", boom)
    assert classify_news("🔴🎥🔺") is None


def test_empty_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky(_text):
        calls["n"] += 1
        return None if calls["n"] < 3 else "politics"

    monkeypatch.setattr(news_classifier, "_request_category", flaky)

    assert classify_news("خبری برای طبقه‌بندی") is NewsCategory.POLITICS
    assert calls["n"] == 3


# پاسخ واقعی یک backend ضعیف: هیچ برچسبی از فهرست در آن نیست.
CHINESE_REFUSAL = "关于这个问题，我没有相关信息，您可以尝试问我其它问题，我会尽力为您解答~"


def test_response_without_label_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def off_script(_text):
        calls["n"] += 1
        return CHINESE_REFUSAL if calls["n"] < 3 else "war_conflict"

    monkeypatch.setattr(news_classifier, "_request_category", off_script)

    assert classify_news("خبری برای طبقه‌بندی") is NewsCategory.WAR_CONFLICT
    assert calls["n"] == 3


def test_persistent_label_less_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_off_script(_text):
        calls["n"] += 1
        return CHINESE_REFUSAL

    monkeypatch.setattr(news_classifier, "_request_category", always_off_script)

    with pytest.raises(RuntimeError):
        classify_news("خبری برای طبقه‌بندی")

    assert calls["n"] == news_classifier.MAX_BAD_RESPONSE_RETRIES + 1


def test_unknown_label_is_a_verdict_not_a_failure(monkeypatch):
    """«unknown» نظر مدل است و نباید مثل پاسخ بد دوباره تلاش شود."""
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def says_unknown(_text):
        calls["n"] += 1
        return "unknown"

    monkeypatch.setattr(news_classifier, "_request_category", says_unknown)

    assert classify_news("تقویم امروز شنبه ۲۸ شهریور ۱۴۰۵") is NewsCategory.UNKNOWN
    assert calls["n"] == 1


def test_persistent_empty_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_empty(_text):
        calls["n"] += 1
        return None

    monkeypatch.setattr(news_classifier, "_request_category", always_empty)

    with pytest.raises(RuntimeError):
        classify_news("خبری برای طبقه‌بندی")

    # یک تلاش اولیه + MAX_BAD_RESPONSE_RETRIES تلاش مجدد
    assert calls["n"] == news_classifier.MAX_BAD_RESPONSE_RETRIES + 1
