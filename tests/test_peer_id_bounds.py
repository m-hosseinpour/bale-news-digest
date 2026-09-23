import pytest

from config import _parse_peer_id


def test_valid_peer_id_is_accepted():
    assert _parse_peer_id("533692756") == 533692756


def test_negative_peer_id_is_accepted():
    assert _parse_peer_id("-42") == -42


@pytest.mark.parametrize("value", ["2147483647", "-2147483648"])
def test_int32_boundaries_are_accepted(value):
    assert _parse_peer_id(value) == int(value)


@pytest.mark.parametrize("value", ["99999999999", "2147483648", "-2147483649"])
def test_out_of_int32_range_is_rejected(value):
    # API بله آیدی را در int32 می‌خواهد؛ بیرون بازه یعنی اجرا باید با پیام واضح
    # متوقف شود، نه اینکه سرور خطای مبهم Go برگرداند.
    assert _parse_peer_id(value) is None


@pytest.mark.parametrize("value", [None, "", "abc", "12.5"])
def test_missing_or_unparseable_peer_id_is_none(value):
    assert _parse_peer_id(value) is None


def test_surrounding_whitespace_is_tolerated():
    # int() خودش فاصله را می‌گیرد؛ پس این حالت خطا نیست.
    assert _parse_peer_id(" 12 ") == 12
