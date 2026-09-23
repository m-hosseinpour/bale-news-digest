import pytest

from model import MediaKind
from news_collector import extract_media

URL = "https://file-gw1.ble.ir/proxy_download/abc=?u=def"


def _doc(mime: str, url: str = URL) -> dict:
    return {"documentMessage": {"url": url, "mimeType": mime}}


def test_photo_document_message():
    # عکس در این API به شکل documentMessage می‌آید، نه photoMessage.
    assert extract_media(_doc("image/jpeg")) == (URL, MediaKind.PHOTO)


def test_video_document_message():
    assert extract_media(_doc("video/mp4")) == (URL, MediaKind.VIDEO)


def test_audio_document_message():
    assert extract_media(_doc("audio/mp3")) == (URL, MediaKind.AUDIO)


def test_unknown_mime_falls_back_to_document():
    assert extract_media(_doc("application/zip")) == (URL, MediaKind.DOCUMENT)


def test_mime_type_case_insensitive():
    assert extract_media(_doc("IMAGE/JPEG")) == (URL, MediaKind.PHOTO)


def test_text_message_has_no_media():
    assert extract_media({"textMessage": {"text": "خبر"}}) is None


def test_empty_message_has_no_media():
    assert extract_media({"emptyMessage": {}}) is None


def test_document_message_without_url_has_no_media():
    assert extract_media({"documentMessage": {"mimeType": "image/jpeg"}}) is None


@pytest.mark.parametrize(
    "message",
    [
        None,
        {},
        {"documentMessage": "not-a-dict"},
        {"documentMessage": {"url": None, "mimeType": "image/jpeg"}},
        {"documentMessage": {"url": "", "mimeType": "image/jpeg"}},
        {"documentMessage": {"url": 123, "mimeType": "image/jpeg"}},
        {"someNewMessage": {"url": URL, "mimeType": "image/jpeg"}},
    ],
)
def test_malformed_payloads_return_none(message):
    assert extract_media(message) is None
