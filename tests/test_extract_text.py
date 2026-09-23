import pytest

from news_collector import extract_text


def test_text_message():
    message = {"textMessage": {"text": "خبر کوتاه"}}
    assert extract_text(message) == "خبر کوتاه"


def test_document_message_with_caption():
    # اکثریت پست‌های کانال از این شکل‌اند؛ نادیده گرفتنش بی‌صدا خبر حذف می‌کند.
    message = {"documentMessage": {"url": "https://file.ble.ir/x", "caption": {"text": "متن ویدیو"}}}
    assert extract_text(message) == "متن ویدیو"


def test_document_message_with_empty_caption():
    assert extract_text({"documentMessage": {"caption": {}}}) == ""
    assert extract_text({"documentMessage": {"caption": {"text": ""}}}) == ""


def test_document_message_with_caption_key_missing():
    assert extract_text({"documentMessage": {"url": "https://file.ble.ir/x"}}) == ""


def test_document_message_with_null_caption_and_value():
    assert extract_text({"documentMessage": {"caption": None}}) == ""
    assert extract_text({"documentMessage": {"caption": {"text": None}}}) == ""


def test_empty_message():
    assert extract_text({"emptyMessage": {}}) == ""


def test_unknown_or_malformed_message():
    assert extract_text({}) == ""
    assert extract_text({"someNewMessage": {"text": "?"}}) == ""
    assert extract_text(None) == ""


def test_text_message_missing_text_key():
    assert extract_text({"textMessage": {}}) == ""


@pytest.mark.parametrize(
    "message",
    [
        {"textMessage": {"text": 123}},
        {"documentMessage": "not-a-dict"},
        {"documentMessage": {"caption": "not-a-dict"}},
    ],
)
def test_malformed_payloads_return_empty_string(message):
    assert extract_text(message) == ""
