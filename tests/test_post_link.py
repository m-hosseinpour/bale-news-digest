import news_summarizer
from model import NewsPost
from news_summarizer import BALE_POST_LINK_TEMPLATE, _post_link


def test_post_link_for_negative_rid():
    # رگرسیون‌پین: rid منفی باید درست به لینک تبدیل شود.
    post = NewsPost(sid="-5395742309641863192-1790163720319", text="x")
    assert _post_link(post) == "https://ble.ir/akharinkhabar/-5395742309641863192/1790163720319"


def test_post_link_for_positive_rid():
    post = NewsPost(sid="1042098241046827171-1789672603195", text="x")
    assert _post_link(post) == "https://ble.ir/akharinkhabar/1042098241046827171/1789672603195"


def test_link_template_uses_configured_channel_slug():
    from config import CHANNEL_SLUG

    assert BALE_POST_LINK_TEMPLATE == f"https://ble.ir/{CHANNEL_SLUG}/{{post_id}}"
    assert news_summarizer.CHANNEL_SLUG == CHANNEL_SLUG
