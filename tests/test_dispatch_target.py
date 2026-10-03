import main
from model import Importance, NewsPost


def _post() -> NewsPost:
    return NewsPost(
        sid="1-1",
        text="خبر",
        importance=Importance.MAJOR,
    )


def _stub_send(monkeypatch, chat_id: int | None) -> list[tuple[str, int]]:
    sent: list[tuple[str, int]] = []

    def fake_send_post(text, media, target) -> None:
        sent.append((text, target))

    monkeypatch.setattr(main, "BALE_BOT_CHAT_ID", chat_id)
    monkeypatch.setattr(main, "summarize_single_post", lambda _post: "خلاصه")
    monkeypatch.setattr(main, "compose_message", lambda _post, _summary: "متن پیام")
    monkeypatch.setattr(main, "send_post", fake_send_post)
    return sent


def test_dispatch_sends_exactly_once_to_the_main_channel(monkeypatch):
    sent = _stub_send(monkeypatch, 555)

    main.dispatch_post(_post())

    assert sent == [("متن پیام", 555)]


def test_dispatch_without_main_channel_sends_nothing(monkeypatch):
    sent = _stub_send(monkeypatch, None)

    main.dispatch_post(_post())

    assert sent == []
