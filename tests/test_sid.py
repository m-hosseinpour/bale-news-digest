import pytest

from news_collector import _build_sid


def test_sid_is_rid_dash_date():
    entry = {"rid": "1042098241046827171", "date": 1789672603195}
    assert _build_sid(entry) == "1042098241046827171-1789672603195"


def test_negative_rid_is_preserved_verbatim():
    # rid ممکن است int64 منفی باشد و باید بدون گرد کردن برگردد؛ قالب sid
    # باید عیناً با news_posts.json موجود یکی باشد وگرنه خبرها دوباره ارسال می‌شوند.
    entry = {"rid": "-5395742309641863192", "date": 1790163720319}
    assert _build_sid(entry) == "-5395742309641863192-1790163720319"


def test_sid_matches_a_real_stored_value():
    entry = {"rid": "-4667486471677404419", "date": 1789672571778}
    assert _build_sid(entry) == "-4667486471677404419-1789672571778"


def test_minus_one_cannot_be_read_as_a_date_separator():
    # قالب قدیمی (جدا کردن تاریخ با split روی «-») با rid منفی می‌شکست.
    entry = {"rid": "-42", "date": 1000}
    assert _build_sid(entry) == "-42-1000"


def test_rid_is_not_rounded_through_float():
    # اگر rid از مسیر float بگذرد، دقتش از دست می‌رود و sid عوض می‌شود.
    rid = "-5395742309641863192"
    entry = {"rid": rid, "date": 1790163720319}
    assert _build_sid(entry).startswith(rid + "-")
    assert str(int(float(rid))) != rid
