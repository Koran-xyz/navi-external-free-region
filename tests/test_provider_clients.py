from src.provider_clients import _extract_gemini_text, _extract_openai_text, configured_providers


def test_extract_gemini_output_text():
    assert _extract_gemini_text({"output_text": "こんにちは"}) == "こんにちは"


def test_extract_gemini_steps_fallback():
    payload = {
        "steps": [
            {
                "type": "model_output",
                "content": [{"text": "検証結果"}],
            }
        ]
    }
    assert _extract_gemini_text(payload) == "検証結果"


def test_extract_openai_output_text():
    assert _extract_openai_text({"output_text": "回答"}) == "回答"


def test_request_scoped_provider_keys_are_detected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    providers = configured_providers({"openai": "openai-test", "gemini": "gemini-test"})
    assert providers["openai"] is True
    assert providers["gemini"] is True
