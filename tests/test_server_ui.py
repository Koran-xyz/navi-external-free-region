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
    assert "API保管庫" in response.text
    assert "Gemini" in response.text
    assert "OpenAI" in response.text
    assert "Copilot" in response.text
    assert "端末内部バックアップから復元" in response.text
    assert "⌂ ホーム" in response.text
    assert "providerTop" in response.text
    assert "migrateLegacyStorage" in response.text
    assert "接続キーが見つかりません" in response.text
    assert response.headers["cache-control"].startswith("no-store")
