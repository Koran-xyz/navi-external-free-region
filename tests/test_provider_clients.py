from src.provider_clients import _extract_gemini_text, _extract_openai_text


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
