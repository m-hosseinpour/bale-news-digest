import pytest

import bale_bot_message_sender as sender
from model import MediaItem, MediaKind

URL = "https://file-gw1.ble.ir/proxy_download/abc=?u=def"


def _item(url: str = URL, kind: MediaKind = MediaKind.PHOTO) -> MediaItem:
    return MediaItem(url=url, kind=kind)


def _capture(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_post(method: str, payload: dict) -> dict:
        calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(sender, "_post", fake_post)
    return calls


def test_text_only_post_uses_send_message(monkeypatch):
    calls = _capture(monkeypatch)

    sender.send_post("متن", [], 123)

    assert len(calls) == 1
    method, payload = calls[0]
    assert method == "sendMessage"
    assert payload["text"] == "متن"
    assert payload["chat_id"] == 123


def test_post_with_photo_uses_send_photo_and_url(monkeypatch):
    calls = _capture(monkeypatch)

    sender.send_post("متن", [_item()], 123)

    method, payload = calls[0]
    assert method == "sendPhoto"
    # لینک خام فرستاده می‌شود؛ خود بله از همان دانلود می‌کند.
    assert payload["photo"] == URL
    assert payload["caption"] == "متن"
    assert "document" not in payload


def test_post_with_video_uses_send_video(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", [_item(kind=MediaKind.VIDEO)], 123)
    method, payload = calls[0]
    assert method == "sendVideo"
    assert payload["video"] == URL


def test_post_with_audio_uses_send_audio(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", [_item(kind=MediaKind.AUDIO)], 123)
    method, payload = calls[0]
    assert method == "sendAudio"
    assert payload["audio"] == URL


def test_post_with_unknown_file_uses_send_document(monkeypatch):
    calls = _capture(monkeypatch)
    sender.send_post("متن", [_item(kind=MediaKind.DOCUMENT)], 123)
    method, payload = calls[0]
    assert method == "sendDocument"
    assert payload["document"] == URL


def test_no_parse_mode_is_sent(monkeypatch):
    # کل متن عادی است و فقط خط لینک مارک‌داون دارد؛ parse_mode نباید ست شود.
    calls = _capture(monkeypatch)
    sender.send_post("متن", [_item()], 123)
    sender.send_post("متن", [], 123)
    for _method, payload in calls:
        assert "parse_mode" not in payload


def test_album_uses_send_media_group_with_caption_on_first_item(monkeypatch):
    calls = _capture(monkeypatch)
    items = [
        _item("https://file-gw1.ble.ir/1"),
        _item("https://file-gw1.ble.ir/2"),
        _item("https://file-gw1.ble.ir/3", kind=MediaKind.VIDEO),
    ]

    sender.send_post("خلاصه", items, 123)

    assert len(calls) == 1
    method, payload = calls[0]
    assert method == "sendMediaGroup"
    assert payload["chat_id"] == 123
    # media باید آرایهٔ واقعی باشد، نه رشتهٔ JSON — بله رشته را رد می‌کند.
    assert isinstance(payload["media"], list)
    assert [entry["type"] for entry in payload["media"]] == ["photo", "photo", "video"]
    assert [entry["media"] for entry in payload["media"]] == [
        "https://file-gw1.ble.ir/1",
        "https://file-gw1.ble.ir/2",
        "https://file-gw1.ble.ir/3",
    ]
    assert payload["media"][0]["caption"] == "خلاصه"
    assert all("caption" not in entry for entry in payload["media"][1:])


@pytest.mark.parametrize(
    ("count", "sizes"),
    [(10, [10]), (11, [6, 5]), (12, [6, 6]), (20, [10, 10]), (21, [7, 7, 7])],
)
def test_album_beyond_ten_items_is_split_without_single_item_chunks(
    monkeypatch, count, sizes
):
    # بله بیش از ۱۰ قلم را با «malformed request» رد می‌کند — و آلبوم تک‌قلمی
    # را هم؛ پس تکه‌بندی «هر ۱۰ قلم» برای ۱۱ قلم می‌شکست ([۱۰, ۱]).
    calls = _capture(monkeypatch)
    items = [_item(f"https://file-gw1.ble.ir/{n}") for n in range(count)]

    sender.send_post("خلاصه", items, 123)

    assert [method for method, _ in calls] == ["sendMediaGroup"] * len(sizes)
    chunks = [payload["media"] for _, payload in calls]
    assert [len(chunk) for chunk in chunks] == sizes
    assert all(len(chunk) >= 2 for chunk in chunks)
    # همهٔ اقلام، به ترتیب، و کپشن فقط روی قلم اول تکهٔ اول.
    assert [entry["media"] for chunk in chunks for entry in chunk] == [
        item.url for item in items
    ]
    assert chunks[0][0]["caption"] == "خلاصه"
    assert all("caption" not in entry for chunk in chunks for entry in chunk[1:])


def test_document_in_a_multi_item_list_raises_a_clear_error(monkeypatch):
    # گروه‌بندی collector هرگز سند به آلبوم نمی‌آورد؛ اگر صدازنندهٔ دیگری این
    # کار را بکند، باید خطای روشن بگیرد نه KeyError.
    _capture(monkeypatch)
    items = [_item(), _item(kind=MediaKind.DOCUMENT)]

    with pytest.raises(ValueError) as excinfo:
        sender.send_post("خلاصه", items, 123)

    assert "document" in str(excinfo.value)
