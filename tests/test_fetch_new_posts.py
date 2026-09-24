import pytest

from model import Importance, MediaKind, NewsPost
from news_collector import _ensure_peer_id, fetch_new_posts
import news_collector


@pytest.fixture(autouse=True)
def _stub_importance(monkeypatch):
    # سنجش اهمیت یک فراخوانی مدل است؛ در تست‌ها جایش را یک حکم ثابت می‌گیرد.
    monkeypatch.setattr(news_collector, "judge_importance", lambda _text: Importance.NORMAL)


def _entry(rid: str, date: int, text: str) -> dict:
    return {"rid": rid, "date": date, "message": {"textMessage": {"text": text}}}


def test_ensure_peer_id_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", None)
    with pytest.raises(RuntimeError) as excinfo:
        _ensure_peer_id()

    message = str(excinfo.value)
    assert "PEER_ID" in message
    assert "resolve_peer_id.py" in message


def test_fetch_new_posts_yields_new_posts(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 5)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 100)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    pages = [
        [_entry("2", 2000, "خبر دو"), _entry("1", 1900, "خبر یک")],
        [],
    ]
    monkeypatch.setattr(news_collector, "load_history", lambda peer_id, date: pages.pop(0))

    posts = list(fetch_new_posts(set()))

    assert [p.sid for p in posts] == ["2-2000", "1-1900"]
    assert [p.text for p in posts] == ["خبر دو", "خبر یک"]


def test_fetch_new_posts_stops_at_first_seen_sid(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    calls: list[int] = []

    def fake_load_history(peer_id: int, date: int) -> list[dict]:
        calls.append(date)
        return [_entry("3", 2000, "خبر سه"), _entry("2", 1990, "خبر دو")]

    monkeypatch.setattr(news_collector, "load_history", fake_load_history)

    # پست «2-1990» قبلاً دیده شده، پس همان‌جا باید بایستیم و پست‌های جدیدتر
    # همان صفحه (3-2000) باید yield شوند.
    posts = list(fetch_new_posts({"2-1990"}))

    assert [p.sid for p in posts] == ["3-2000"]
    assert len(calls) == 1


def test_fetch_new_posts_skips_empty_text(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    pages = [
        [
            {"rid": "3", "date": 2000, "message": {"emptyMessage": {}}},
            {"rid": "2", "date": 1990, "message": {"documentMessage": {"caption": {}}}},
            {"rid": "1", "date": 1980, "message": {"documentMessage": {"caption": {"text": "ویدیو"}}}},
        ],
        [],
    ]
    monkeypatch.setattr(news_collector, "load_history", lambda peer_id, date: pages.pop(0))

    posts = list(fetch_new_posts(set()))

    assert [p.sid for p in posts] == ["1-1980"]
    assert posts[0].text == "ویدیو"


def test_fetch_new_posts_advances_anchor(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    anchors: list[int] = []

    def fake_load_history(peer_id: int, date: int) -> list[dict]:
        anchors.append(date)
        if len(anchors) == 1:
            return [_entry("2", 2000, "الف"), _entry("1", 1990, "ب")]
        return []

    monkeypatch.setattr(news_collector, "load_history", fake_load_history)
    list(fetch_new_posts(set()))

    assert anchors[1] == 1989


def test_fetch_new_posts_respects_page_cap(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 2)

    pages_sent = 0

    def fake_load_history(peer_id: int, date: int) -> list[dict]:
        nonlocal pages_sent
        pages_sent += 1
        base = 10_000 - pages_sent * 100
        return [_entry(str(base), base, f"خبر {base}")]

    monkeypatch.setattr(news_collector, "load_history", fake_load_history)
    posts = list(fetch_new_posts(set()))

    assert pages_sent == 2
    assert len(posts) == 2


def test_fetch_new_posts_respects_post_cap(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 3)

    page = [_entry(str(d), d, f"خبر {d}") for d in range(2000, 1980, -1)]
    monkeypatch.setattr(news_collector, "load_history", lambda peer_id, date: list(page))

    posts = list(fetch_new_posts(set()))

    assert len(posts) == 3


def test_fetch_new_posts_raises_when_pagination_stalls(monkeypatch):
    # سرور همان صفحهٔ تکراری را برمی‌گرداند (anchor جلو نمی‌رود)؛ بدون این گارد
    # حلقه تا سقف MAX_PAGES_PER_RUN روی یک صفحه می‌ماند.
    # توجه: این تست تلهٔ «جا افتادن منهای یک» را پین نمی‌کند — آن تله فقط یک
    # ردیف تکراری اضافه می‌کند (چون date کران شامل است) و در
    # test_fetch_new_posts_advances_anchor پین شده است.
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(
        news_collector,
        "load_history",
        lambda peer_id, date: [_entry("2", 2000, "الف"), _entry("1", 1990, "ب")],
    )

    with pytest.raises(RuntimeError) as excinfo:
        list(fetch_new_posts(set()))

    assert "صفحه‌بندی" in str(excinfo.value)


def test_fetch_new_posts_propagates_network_error(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    def boom(peer_id: int, date: int) -> list[dict]:
        raise RuntimeError("⛔ واکشی تاریخچه از API بله ناموفق بود")

    monkeypatch.setattr(news_collector, "load_history", boom)

    with pytest.raises(RuntimeError):
        list(fetch_new_posts(set()))


def test_fetch_new_posts_attaches_media(monkeypatch):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    url = "https://file-gw1.ble.ir/proxy_download/abc=?u=def"
    pages = [
        [
            {
                "rid": "1",
                "date": 2000,
                "message": {
                    "documentMessage": {
                        "url": url,
                        "mimeType": "image/jpeg",
                        "caption": {"text": "خبر با عکس"},
                    }
                },
            },
            _entry("2", 1990, "خبر بدون ضمیمه"),
        ],
        [],
    ]
    monkeypatch.setattr(news_collector, "load_history", lambda peer_id, date: pages.pop(0))

    posts = list(fetch_new_posts(set()))

    with_media = next(p for p in posts if p.sid == "1-2000")
    without_media = next(p for p in posts if p.sid == "2-1990")
    assert with_media.media_url == url
    assert with_media.media_kind is MediaKind.PHOTO
    assert without_media.media_url is None
    assert without_media.media_kind is None


def test_news_post_model_roundtrip_for_negative_rid():
    post = NewsPost(sid="-42-1000", text="خبر")
    assert post.sid == "-42-1000"


def test_same_rid_with_two_dates_yields_both_posts(monkeypatch):
    # یک rid می‌تواند روی دو ردیف با تاریخ‌های متفاوت بیاید و هر دو در
    # news_posts.json ذخیره شده باشند؛ dedup نباید روی rid انجام شود.
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 5)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 100)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)

    pages = [
        [_entry("7", 2000, "خبر الف"), _entry("7", 1999, "خبر ب")],
        [],
    ]
    monkeypatch.setattr(
        news_collector, "load_history", lambda peer_id, date: list(pages.pop(0))
    )

    posts = list(fetch_new_posts(set()))

    assert [p.sid for p in posts] == ["7-2000", "7-1999"]
    assert [p.text for p in posts] == ["خبر الف", "خبر ب"]
