from src.integrations.openai_status import INVALID_KEY_HINT, public_openai_error


def test_generic_openai_error_does_not_echo_exception_text() -> None:
    text = public_openai_error(RuntimeError("Incorrect API key provided: sk-proj-SECRETVusA"))
    assert text == "OpenAI request failed."
    assert "SECRET" not in text


def test_invalid_key_hint_does_not_include_secret() -> None:
    assert "OPENAI_API_KEY" in INVALID_KEY_HINT
    assert "sk-" not in INVALID_KEY_HINT
