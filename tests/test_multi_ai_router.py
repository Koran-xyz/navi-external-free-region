from src.multi_ai_router import choose_provider
from src.provider_clients import configured_providers


def test_configured_providers_shape():
    providers = configured_providers()
    assert set(providers) == {"openai", "gemini", "copilot"}
    assert all(isinstance(value, bool) for value in providers.values())
