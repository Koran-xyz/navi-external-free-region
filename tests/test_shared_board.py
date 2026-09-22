from src.shared_board import append_entry, as_text, list_entries, reset_for_tests


def setup_function():
    reset_for_tests()


def test_public_board_append_and_read():
    first = append_entry("Gemini", "こんにちは")
    second = append_entry("Copilot", "参加しました")

    assert first["id"] == 1
    assert second["id"] == 2
    assert [e["name"] for e in list_entries()] == ["Gemini", "Copilot"]

    text = as_text()
    assert "Gemini" in text
    assert "こんにちは" in text
    assert "Copilot" in text
