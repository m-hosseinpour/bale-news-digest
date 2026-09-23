from model import MediaKind, NewsPost
from news_summarizer import _media_hint, compose_message


def _post(sid: str = "1042098241046827171-1789672603195") -> NewsPost:
    return NewsPost(sid=sid, text="خبر", category=None)


def test_compose_keeps_summary_untouched():
    # متن خلاصه نباید دست‌کاری شود؛ فقط لینک مارک‌داون به آخر پیام اضافه می‌شود.
    summary = "وزیر خارجه ایران (عراقچی) دیدار کرد. طرفین درباره غزه - و تحولات - گفت‌وگو کردند."
    message = compose_message(_post(), summary)
    assert message.startswith(summary + "\n\n")


def test_compose_appends_markdown_link():
    message = compose_message(_post(), "خبر")
    lines = message.split("\n\n")
    assert lines[-1] == (
        "[لینک خبر مرجع](https://ble.ir/akharinkhabar/"
        "1042098241046827171/1789672603195)"
    )


def test_compose_does_not_escape_anything():
    message = compose_message(_post(), "خبر.")
    assert "خبر." in message
    assert "\\" not in message


def test_media_hint_per_kind():
    assert _media_hint(MediaKind.PHOTO) == "\n\n[این خبر همراه یک عکس است.]"
    assert _media_hint(MediaKind.VIDEO) == "\n\n[این خبر همراه یک ویدیو است.]"
    assert _media_hint(MediaKind.AUDIO) == "\n\n[این خبر همراه یک فایل صوتی است.]"
    assert _media_hint(MediaKind.DOCUMENT) == "\n\n[این خبر همراه یک فایل است.]"


def test_media_hint_empty_when_no_media():
    assert _media_hint(None) == ""
