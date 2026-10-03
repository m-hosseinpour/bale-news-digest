"""آلبوم در LoadHistory چند ردیف پشت‌سرهم است، نه یک ردیف.

شکل واقعی (کانال akharinkhabar، ۲۴ ساعت، ۱۶ آلبوم): ردیف‌ها فاصلهٔ ۱ تا ۷
میلی‌ثانیه دارند و فقط قدیمی‌ترینشان کپشن دارد. بدون گروه‌بندی، بقیهٔ ردیف‌ها
بی‌متن‌اند و دور ریخته می‌شوند.
"""

import pytest

from model import Importance, MediaKind
import news_collector
from news_collector import fetch_new_posts

PHOTO = "image/jpeg"
VIDEO = "video/mp4"


@pytest.fixture(autouse=True)
def _stub_importance(monkeypatch):
    monkeypatch.setattr(
        news_collector, "judge_importance", lambda _text: Importance.NORMAL
    )


def _media(rid: str, date: int, mime: str = PHOTO, caption: str = "") -> dict:
    return {
        "rid": rid,
        "date": date,
        "message": {
            "documentMessage": {
                "url": f"https://file-gw1.ble.ir/{rid}",
                "mimeType": mime,
                "caption": {"text": caption},
            }
        },
    }


def _text(rid: str, date: int, text: str) -> dict:
    return {"rid": rid, "date": date, "message": {"textMessage": {"text": text}}}


def _fetch(monkeypatch, pages: list[list[dict]]) -> list:
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 5)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 100)
    monkeypatch.setattr(
        news_collector, "load_history", lambda peer_id, date: list(pages.pop(0))
    )
    return list(fetch_new_posts(set()))


def test_album_siblings_join_the_captioned_row(monkeypatch):
    # همان آلبوم گزارش‌شده: کپشن روی قدیمی‌ترین ردیف، بقیه بی‌متن.
    page = [
        _media("4", 2003),
        _media("3", 2002),
        _media("2", 2001),
        _media("1", 2000, caption="تصاویر خسارت"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert len(posts) == 1
    post = posts[0]
    assert post.sid == "1-2000"
    assert post.text == "تصاویر خسارت"
    # ترتیب ارسال باید مثل کانال مبدأ باشد: قدیمی‌ترین (دارای کپشن) اول.
    assert [m.url for m in post.media] == [
        "https://file-gw1.ble.ir/1",
        "https://file-gw1.ble.ir/2",
        "https://file-gw1.ble.ir/3",
        "https://file-gw1.ble.ir/4",
    ]
    assert {m.kind for m in post.media} == {MediaKind.PHOTO}


def test_album_spanning_two_pages_stays_one_post(monkeypatch):
    # آلبوم ۱۰ قلمی روزنامه‌ها همیشه از مرز صفحه (۱۰ ردیف) می‌گذرد.
    page1 = [_media(str(d), d) for d in range(2009, 2004, -1)]
    page2 = [_media(str(d), d) for d in range(2004, 1999, -1)]
    page2[-1]["message"]["documentMessage"]["caption"]["text"] = "صفحه نخست روزنامه‌ها"

    posts = _fetch(monkeypatch, [page1, page2, []])

    assert len(posts) == 1
    assert posts[0].sid == "2000-2000"
    assert len(posts[0].media) == 10


def test_mixed_photo_video_album_stays_one_post(monkeypatch):
    page = [
        _media("2", 2001, mime=VIDEO),
        _media("1", 2000, mime=PHOTO, caption="گزارش تصویری"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert len(posts) == 1
    assert [m.kind for m in posts[0].media] == [MediaKind.PHOTO, MediaKind.VIDEO]


def test_lone_captionless_media_row_is_dropped(monkeypatch):
    # ردیف بی‌متن بدون آلبوم هیچ خبری ندارد؛ مثل قبل دور ریخته می‌شود.
    page = [_media("1", 2000)]
    assert _fetch(monkeypatch, [page, []]) == []


def test_gap_beyond_album_window_is_not_an_album(monkeypatch):
    page = [
        _media("2", 2000 + news_collector.ALBUM_GAP_MS + 1),
        _media("1", 2000, caption="خبر"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert len(posts) == 1
    assert [m.url for m in posts[0].media] == ["https://file-gw1.ble.ir/1"]


def test_two_captioned_posts_inside_the_window_stay_separate(monkeypatch):
    page = [
        _media("2", 2001, caption="خبر دوم"),
        _media("1", 2000, caption="خبر اول"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert [p.sid for p in posts] == ["2-2001", "1-2000"]
    assert [len(p.media) for p in posts] == [1, 1]


def test_text_only_post_between_media_rows_breaks_the_album(monkeypatch):
    # ردیف متنی در میانه، زنجیرهٔ آلبوم را قطع می‌کند: ردیف بی‌متن بعدش آلبوم نیست.
    page = [
        _media("3", 2002),
        _text("2", 2001, "خبر متنی"),
        _media("1", 2000, caption="خبر با عکس"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert [p.sid for p in posts] == ["2-2001", "1-2000"]
    assert len(posts[1].media) == 1


def test_document_rows_are_not_grouped(monkeypatch):
    # آلبوم سند/صوت تست زنده نشده و گروه کردنشان ریسک خطای ارسال دارد؛
    # رفتار قبلی می‌ماند: فقط ردیف دارای کپشن می‌رود.
    page = [
        _media("2", 2001, mime="application/pdf"),
        _media("1", 2000, mime="application/pdf", caption="فایل گزارش"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert len(posts) == 1
    assert len(posts[0].media) == 1
    assert posts[0].media[0].kind is MediaKind.DOCUMENT


def test_album_of_one_is_a_plain_media_post(monkeypatch):
    page = [_media("1", 2000, caption="خبر با عکس")]
    posts = _fetch(monkeypatch, [page, []])

    assert len(posts) == 1
    assert len(posts[0].media) == 1


def test_two_albums_inside_one_window_stay_separate(monkeypatch):
    page = [
        _media("4", 2003),
        _media("3", 2002, caption="آلبوم دوم"),
        _media("2", 2001),
        _media("1", 2000, caption="آلبوم اول"),
    ]
    posts = _fetch(monkeypatch, [page, []])

    assert [p.sid for p in posts] == ["3-2002", "1-2000"]
    assert [[m.url for m in p.media] for p in posts] == [
        ["https://file-gw1.ble.ir/3", "https://file-gw1.ble.ir/4"],
        ["https://file-gw1.ble.ir/1", "https://file-gw1.ble.ir/2"],
    ]


def test_album_whose_head_is_already_seen_sends_nothing(monkeypatch):
    # آلبومی که سرش (ردیف دارای کپشن) قبلاً فرستاده و ذخیره شده: ردیف‌های
    # بی‌متن جدیدتر سرِ بی‌کپشن می‌مانند و دور ریخته می‌شوند — نه ارسال جزئی.
    page = [_media("3", 2002), _media("2", 2001), _media("1", 2000, caption="خبر")]
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(
        news_collector, "load_history", lambda peer_id, date: list(page)
    )

    assert list(fetch_new_posts({"1-2000"})) == []


def test_album_caption_that_normalizes_to_empty_drops_the_whole_album(monkeypatch):
    # کپشنی که فقط امضای تبلیغاتی کانال است متن خبری ندارد؛ پس آلبومش هم نمی‌رود.
    page = [
        _media("2", 2001),
        _media("1", 2000, caption="@Akharinkhabar | akharinkhabar.ir"),
    ]
    assert _fetch(monkeypatch, [page, []]) == []


def test_post_cap_counts_an_album_as_one_post(monkeypatch):
    page = [
        _text("9", 3000, "خبر متنی"),
        _media("3", 2002),
        _media("2", 2001),
        _media("1", 2000, caption="خبر با چهار عکس"),
    ]
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 2)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 1)
    monkeypatch.setattr(
        news_collector, "load_history", lambda peer_id, date: list(page)
    )

    posts = list(fetch_new_posts(set()))

    assert [p.sid for p in posts] == ["9-3000", "1-2000"]
    assert len(posts[1].media) == 3
