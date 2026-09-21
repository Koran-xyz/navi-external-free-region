from fastapi.testclient import TestClient

from server.app import app


client = TestClient(app)


def test_public_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["providers"]) == {"openai", "gemini", "copilot"}


def test_browser_ui_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Navi Multi-AI Chat" in response.text
    assert "⌂ ホーム" in response.text
    assert "GATEWAY_CHAT_KEY" in response.text
    assert "GEMINI_API_KEY" in response.text
    assert "OPENAI_API_KEY" in response.text
    assert "このキーを保存" in response.text
    assert "providerTop" in response.text
    assert "保存しても勝手に戻りません" in response.text
