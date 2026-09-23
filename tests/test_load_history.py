import pytest

from news_collector import _validate_history, load_history


def _entry(rid: str, date: int) -> dict:
    return {"rid": rid, "date": date, "message": {"emptyMessage": {}}}


def test_empty_history_is_end_of_history():
    assert _validate_history({"history": []}, anchor_ms=1000) == []


def test_valid_page_is_returned():
    anchor = 2000
    history = [_entry("a", 2000), _entry("b", 1990)]
    assert _validate_history({"history": history}, anchor_ms=anchor) == history


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "not-a-dict",
        42,
        None,
        {"history": None},
        {"history": {}},
        {"history": "x"},
        {},
        {"other": []},
    ],
)
def test_malformed_payload_raises(payload):
    with pytest.raises(RuntimeError):
        _validate_history(payload, anchor_ms=1000)


def test_page_newer_than_anchor_raises():
    # anchor_next = min(date) - 1 باید اکیداً عقب برود؛ اگر صفحه‌ای تماماً
    # جدیدتر از anchor برگردد یعنی سرور date را نادیده گرفته و صفحه‌بندی
    # تا ابد روی همان پیام‌ها می‌ماند.
    anchor = 1000
    with pytest.raises(RuntimeError):
        _validate_history({"history": [_entry("a", 1001), _entry("b", 2000)]}, anchor_ms=anchor)


def test_message_exactly_at_anchor_is_fine():
    # date یک کران بالا و شامل است؛ پیام دقیقاً روی anchor یعنی صفحهٔ بعد
    # از anchor - 1 شروع می‌شود، پس صفحه پیش رفته است.
    history = [_entry("a", 1000), _entry("b", 990)]
    assert _validate_history({"history": history}, anchor_ms=1000) == history


def test_missing_or_bad_date_raises():
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"rid": "a"}]}, anchor_ms=1000)
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"rid": "a", "date": "1000"}]}, anchor_ms=1000)
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"date": 5}]}, anchor_ms=1000)


def test_missing_rid_raises():
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"date": 5}]}, anchor_ms=1000)
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"rid": 5, "date": 5}]}, anchor_ms=1000)


def test_non_dict_entry_raises():
    with pytest.raises(RuntimeError):
        _validate_history({"history": ["x"]}, anchor_ms=1000)


def test_load_history_raises_on_network_error(monkeypatch):
    import news_collector

    def boom(*args, **kwargs):
        raise news_collector.requests.ConnectionError("no network")

    monkeypatch.setattr(news_collector.requests, "post", boom)
    with pytest.raises(RuntimeError):
        load_history(1, 1000)


def test_load_history_raises_on_invalid_json(monkeypatch):
    import news_collector

    class Response:
        content = b"<html>not json</html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(news_collector.requests, "post", lambda *a, **k: Response())
    with pytest.raises(RuntimeError):
        load_history(1, 1000)


def test_load_history_raises_on_http_error(monkeypatch):
    import news_collector

    class Response:
        def raise_for_status(self):
            raise news_collector.requests.HTTPError("400 Bad Request")

    monkeypatch.setattr(news_collector.requests, "post", lambda *a, **k: Response())
    with pytest.raises(RuntimeError):
        load_history(1, 1000)


def test_load_history_sends_expected_request_body(monkeypatch):
    import news_collector

    captured = {}

    class Response:
        content = b'{"history": [{"rid": "-1", "date": 999, "message": {"emptyMessage": {}}}]}'

        def raise_for_status(self):
            return None

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return Response()

    monkeypatch.setattr(news_collector.requests, "post", fake_post)
    history = load_history(533692756, 1000)

    assert captured["url"] == "https://api.ble.ir/api/v1/LoadHistory"
    assert captured["json"] == {"peer": {"type": 2, "id": 533692756}, "date": 1000}
    assert captured["headers"]["Content-Type"] == "application/json"
    assert history == [{"rid": "-1", "date": 999, "message": {"emptyMessage": {}}}]


def test_unknown_message_shape_raises():
    # شکل تازه/تغییرنام‌یافتهٔ message باید خطا بدهد، نه اینکه پست بی‌صدا حذف
    # شود و تاریخچه «تمام‌شده» به نظر برسد.
    with pytest.raises(RuntimeError) as excinfo:
        _validate_history(
            {"history": [{"rid": "a", "date": 1000, "message": {"videoMessage": {"url": "x"}}}]},
            anchor_ms=1000,
        )
    assert "message" in str(excinfo.value)


def test_missing_message_key_raises():
    with pytest.raises(RuntimeError):
        _validate_history({"history": [{"rid": "a", "date": 1000}]}, anchor_ms=1000)


def test_non_dict_message_raises():
    with pytest.raises(RuntimeError):
        _validate_history(
            {"history": [{"rid": "a", "date": 1000, "message": "not-a-dict"}]},
            anchor_ms=1000,
        )


def test_empty_dict_message_is_accepted_as_no_content():
    # در داده واقعی message خالی هم دیده می‌شود (حدود ۰٫۱٪) و یعنی «بدون محتوا».
    # این نباید اجرا را متوقف کند.
    history = [{"rid": "a", "date": 1000, "message": {}}]
    assert _validate_history({"history": history}, anchor_ms=1000) == history


@pytest.mark.parametrize(
    "message",
    [{"emptyMessage": {}}, {"textMessage": {"text": "x"}}, {"documentMessage": {"caption": {"text": "x"}}}],
)
def test_known_message_shapes_are_accepted(message):
    history = [{"rid": "a", "date": 1000, "message": message}]
    assert _validate_history({"history": history}, anchor_ms=1000) == history
