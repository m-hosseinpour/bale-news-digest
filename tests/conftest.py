import pytest

from open_ai_client_provider import open_ai_client


@pytest.fixture(autouse=True)
def _no_real_model_calls(monkeypatch):
    """هر تستی که فراخوانی مدل را stub نکند، بلند شکست می‌خورد.

    بدون این گارد، تست‌های collector واقعاً به گیتوی درخواست می‌زدند (و
    «unit tests, no network» در README دروغ می‌شد).
    """

    def boom(*_args, **_kwargs):
        raise AssertionError("این تست فراخوانی واقعی مدل می‌زند؛ آن را monkeypatch کن")

    monkeypatch.setattr(open_ai_client.chat.completions, "create", boom)
