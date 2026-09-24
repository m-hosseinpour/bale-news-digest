import pytest

import news_classifier
import news_collector
import main
from model import Importance, NewsCategory, NewsPost
from news_classifier import _match_importance, judge_importance


# ---------- _match_importance ----------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("major", Importance.MAJOR),
        ("normal", Importance.NORMAL),
        ("trivial", Importance.TRIVIAL),
        ("Major", Importance.MAJOR),
        ("Normal.", Importance.NORMAL),
        ("  trivial  ", Importance.TRIVIAL),
        ("This is a major news event.", Importance.MAJOR),
        ("I would say: normal\n", Importance.NORMAL),
    ],
)
def test_match_importance_accepts_weak_model_forms(raw, expected):
    assert _match_importance(raw) is expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "majority",  # باید کل‌واژه باشد، نه زیررشته
        "triviality",
        "关于这个问题，我没有相关信息",
        "no answer",
        # نفی: مدل با رد کردن یک برچسب، همان برچسب را به ما می‌دهد. خواندنش
        # یعنی حذف خبری که مدل گفته کمارزش نیست.
        "not trivial",
        "This is not trivial; it is a war escalation",
        "not normal",
    ],
)
def test_match_importance_rejects_unparseable(raw):
    assert _match_importance(raw) is None


def test_match_importance_reads_the_label_after_a_negated_one():
    assert _match_importance("not normal, this is major") is Importance.MAJOR
    assert _match_importance("normal, not trivial") is Importance.NORMAL


# ---------- judge_importance ----------

CHINESE_REFUSAL = "关于这个问题，我没有相关信息，您可以尝试问我其它问题，我会尽力为您解答~"


def test_importance_empty_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def flaky(_text):
        calls["n"] += 1
        return None if calls["n"] < 3 else "major"

    monkeypatch.setattr(news_classifier, "_request_importance", flaky)

    assert judge_importance("خبری برای سنجش اهمیت") is Importance.MAJOR
    assert calls["n"] == 3


def test_importance_label_less_response_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def off_script(_text):
        calls["n"] += 1
        return CHINESE_REFUSAL if calls["n"] < 2 else "trivial"

    monkeypatch.setattr(news_classifier, "_request_importance", off_script)

    assert judge_importance("خبری برای سنجش اهمیت") is Importance.TRIVIAL
    assert calls["n"] == 2


def test_importance_persistent_bad_response_raises_after_retries(monkeypatch):
    monkeypatch.setattr(news_classifier.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def always_empty(_text):
        calls["n"] += 1
        return None

    monkeypatch.setattr(news_classifier, "_request_importance", always_empty)

    with pytest.raises(RuntimeError):
        judge_importance("خبری برای سنجش اهمیت")

    assert calls["n"] == news_classifier.MAX_BAD_RESPONSE_RETRIES + 1


def test_importance_of_content_free_text_is_none_without_calling_model(monkeypatch):
    def boom(_text):
        raise AssertionError("نباید برای متن بدون محتوا به مدل درخواست بزند")

    monkeypatch.setattr(news_classifier, "_request_importance", boom)
    assert judge_importance("🔴🎥🔺") is None


# ---------- NewsPost model ----------


def test_news_post_parses_importance():
    post = NewsPost(sid="1-1", text="خبر", category=NewsCategory.POLITICS, importance="major")
    assert post.importance is Importance.MAJOR


def test_news_post_importance_defaults_to_none():
    post = NewsPost(sid="1-1", text="خبر", category=NewsCategory.POLITICS)
    assert post.importance is None


def test_news_post_invalid_importance_falls_back_to_none():
    post = NewsPost(sid="1-1", text="خبر", category=NewsCategory.POLITICS, importance="urgent")
    assert post.importance is None


# ---------- gate in main ----------


def _post(importance: Importance | None) -> NewsPost:
    return NewsPost(
        sid="1-1", text="خبر", category=NewsCategory.POLITICS, importance=importance
    )


def test_gate_sends_when_importance_is_unknown(monkeypatch):
    # fail-open: خرابیِ سنجش نباید خبر را بی‌صدا حذف کند.
    monkeypatch.setattr(main, "MIN_IMPORTANCE", Importance.MAJOR)
    assert main._meets_importance(_post(None)) is True


def test_gate_threshold_major_only(monkeypatch):
    monkeypatch.setattr(main, "MIN_IMPORTANCE", Importance.MAJOR)
    assert main._meets_importance(_post(Importance.MAJOR)) is True
    assert main._meets_importance(_post(Importance.NORMAL)) is False
    assert main._meets_importance(_post(Importance.TRIVIAL)) is False


def test_gate_threshold_normal(monkeypatch):
    monkeypatch.setattr(main, "MIN_IMPORTANCE", Importance.NORMAL)
    assert main._meets_importance(_post(Importance.MAJOR)) is True
    assert main._meets_importance(_post(Importance.NORMAL)) is True
    assert main._meets_importance(_post(Importance.TRIVIAL)) is False


def test_run_once_dispatches_only_posts_that_pass_the_gate(monkeypatch):
    """گِیت را در مسیر واقعی run_once قفل می‌کند.

    بدون این تست، حذف `and _meets_importance(...)` از run_once هیچ تستی را
    قرمز نمی‌کرد.
    """
    monkeypatch.setattr(main, "MIN_IMPORTANCE", Importance.MAJOR)

    posts = [
        NewsPost(
            sid="1-1", text="خبر مهم", category=NewsCategory.POLITICS,
            importance=Importance.MAJOR,
        ),
        NewsPost(
            sid="2-2", text="خبر عادی", category=NewsCategory.POLITICS,
            importance=Importance.NORMAL,
        ),
        NewsPost(
            sid="3-3", text="خبر با سنجش شکست‌خورده", category=NewsCategory.WAR_CONFLICT,
            importance=None,
        ),
        NewsPost(
            sid="4-4", text="خبر ورزشی", category=NewsCategory.SPORTS,
            importance=None,
        ),
    ]

    dispatched: list[NewsPost] = []
    monkeypatch.setattr(main, "load_posts", lambda: [])
    monkeypatch.setattr(main, "save_posts", lambda _posts: None)
    monkeypatch.setattr(main, "dispatch_post", dispatched.append)
    monkeypatch.setattr(main, "fetch_new_posts", lambda _seen: iter(posts))

    main.run_once()

    # مهم فرستاده می‌شود، عادی نه، سنجش‌نشده (fail-open) فرستاده می‌شود، و
    # دستهٔ غیرمهم هرگز نمی‌رود.
    assert [p.sid for p in dispatched] == ["1-1", "3-3"]


# ---------- collector wiring ----------


def _entry(rid: str, date: int, text: str) -> dict:
    return {"rid": rid, "date": date, "message": {"textMessage": {"text": text}}}


def _collect(monkeypatch, category, history):
    monkeypatch.setattr(news_collector, "PEER_ID", 1)
    monkeypatch.setattr(news_collector, "HISTORY_PAGE_SLEEP", 0)
    monkeypatch.setattr(news_collector, "MAX_PAGES_PER_RUN", 5)
    monkeypatch.setattr(news_collector, "MAX_POSTS_PER_RUN", 100)
    monkeypatch.setattr(news_collector, "classify_news", lambda _t: category)
    pages = [history, []]
    monkeypatch.setattr(news_collector, "load_history", lambda _p, _d: pages.pop(0))
    return list(news_collector.fetch_new_posts(set()))


def test_collector_judges_importance_for_important_category(monkeypatch):
    monkeypatch.setattr(news_collector, "judge_importance", lambda _t: Importance.MAJOR)

    posts = _collect(
        monkeypatch, NewsCategory.POLITICS, [_entry("1", 2000, "خبر مهم")]
    )

    assert posts[0].importance is Importance.MAJOR


def test_collector_skips_importance_for_non_important_category(monkeypatch):
    def boom(_text):
        raise AssertionError("برای دستهٔ غیرمهم نباید اهمیت سنجیده شود")

    monkeypatch.setattr(news_collector, "judge_importance", boom)

    posts = _collect(
        monkeypatch, NewsCategory.SPORTS, [_entry("1", 2000, "خبر ورزشی")]
    )

    assert posts[0].importance is None


def test_collector_importance_failure_is_fail_open(monkeypatch):
    def boom(_text):
        raise RuntimeError("گیتوی خراب است")

    monkeypatch.setattr(news_collector, "judge_importance", boom)

    posts = _collect(
        monkeypatch, NewsCategory.POLITICS, [_entry("1", 2000, "خبر مهم")]
    )

    # پست با importance=None ذخیره می‌شود و در main فرستاده خواهد شد.
    assert posts[0].importance is None
    assert posts[0].category is NewsCategory.POLITICS
