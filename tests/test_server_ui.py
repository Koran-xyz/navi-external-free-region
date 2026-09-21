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
