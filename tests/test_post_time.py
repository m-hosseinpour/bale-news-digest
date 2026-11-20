from post_time import format_post_time, gregorian_to_jalali


def test_gregorian_to_jalali_known_dates():
    # نوروز، تاریخ واقعی حملهٔ پتروشیمی جم در همین پروژه، و یک تاریخ قدیمی.
    assert gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)
    assert gregorian_to_jalali(2026, 4, 6) == (1405, 1, 17)
    assert gregorian_to_jalali(2026, 11, 19) == (1405, 8, 28)
    assert gregorian_to_jalali(1979, 2, 11) == (1357, 11, 22)
    # آخرین روز سال ۱۴۰۴ و اول فروردین ۱۴۰۵، دو طرف مرز سال.
    assert gregorian_to_jalali(2026, 3, 20) == (1404, 12, 29)


def test_format_post_time_is_persian_and_tehran_local():
    # 1795098193219 = 2026-11-19T14:23:13Z = 17:53 به وقت تهران.
    assert format_post_time(1795098193219) == (
        "۲۸ آبان ۱۴۰۵، ساعت ۱۷:۵۳ به وقت تهران (2026-11-19)"
    )
