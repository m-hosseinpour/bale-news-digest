import bale_bot_message_sender as sender
from model import MediaKind

URL = "https://file-gw1.ble.ir/proxy_download/abc=?u=def"


def _capture(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_post(method: str, payload: dict) -> dict:
        calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(sender, "_post", fake_post)
    return calls


def test_text_only_post_uses_send_message(monkeypatch):
    calls = _capture(monkeypatch)

    sender.send_post("متن", None, None, 123)

    assert len(calls) == 1
    method, payload = calls[0]
    assert method == "sendMessage"
    assert payload["text"] == "متن"
    assert payload["chat_id"] == 123


def test_post_with_photo_uses_send_photo_and_url(monkeypatch):
    calls = _capture(monkeypatch)

    sender.send_post("متن", URL, MediaKind.PHOTO, 123)

    method, payload = calls[0]
    assert method == "sendPhoto"
    # لینک خام فرستاده می‌شود؛ خود بله از همان دانلود می‌کند.
    assert payload["photo"] == URL
    assert payload["caption"] == "متن"
    assert "document" not in payload


def test_post_with_video_uses_send_video(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", URL, MediaKind.VIDEO, 123)
    method, payload = calls[0]
    assert method == "sendVideo"
    assert payload["video"] == URL


def test_post_with_audio_uses_send_audio(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", URL, MediaKind.AUDIO, 123)
    method, payload = calls[0]
    assert method == "sendAudio"
    assert payload["audio"] == URL


def test_post_with_unknown_file_uses_send_document(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", URL, MediaKind.DOCUMENT, 123)
    method, payload = calls[0]
    assert method == "sendDocument"
    assert payload["document"] == URL


def test_url_without_kind_falls_back_to_text(monkeypatch):
    # گارد: اگر فقط یکی از دو فیلد پر باشد، نباید به متد رسانه‌ای برود.
    calls = _capture(monkeypatch)
    sender.send_post("متن", URL, None, 123)
    assert calls[0][0] == "sendMessage"


def test_kind_without_url_falls_back_to_text(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", None, MediaKind.PHOTO, 123)
    assert calls[0][0] == "sendMessage"


def test_no_parse_mode_is_sent(monkeypatch):
    # کل متن عادی است و فقط خط لینک مارک‌داون دارد؛ parse_mode نباید ست شود.
    calls = _capture(monkeypatch)
    sender.send_post("متن", URL, MediaKind.PHOTO, 123)
    sender.send_post("متن", None, None, 123)
    for _method, payload in calls:
        assert "parse_mode" not in payload
