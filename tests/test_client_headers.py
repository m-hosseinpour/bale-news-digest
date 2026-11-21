from open_ai_client_provider import LLM_SESSION_ID, LLM_USER_AGENT, open_ai_client


def test_client_identifies_itself_and_sends_a_session_id():
    """Go این دو هدر را برای مسیریابی و کش پرامپت می‌خواهد.

    کلاینت مشترک یک‌بار ساخته می‌شود؛ اگر بازسازی‌اش کسی این هدرها را جا
    بیندازد، هیچ تست دیگری خبر نمی‌دهد و فقط کش و مسیریابی Go کورکورانه
    خراب می‌شود.
    """
    headers = {key.lower(): value for key, value in open_ai_client.default_headers.items()}

    assert headers["user-agent"] == LLM_USER_AGENT
    assert headers["x-opencode-session"] == LLM_SESSION_ID
