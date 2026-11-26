import os
import tempfile

from src.gcgw_workspace import append_board, append_work, list_board, list_work, snapshot


def _db():
    fd, path = tempfile.mkstemp(prefix="gcgw-", suffix=".db")
    os.close(fd)
    os.environ["GCGW_DB_PATH"] = path
    return path


def test_universal_board_and_work_table():
    path = _db()
    try:
        b = append_board("Gemini", "TEST", "hello", "MESSAGE")
        w = append_work("Gemini", "TEST", "task", "WORKING", "doing", "next")
        assert b["trust"] == "UNVERIFIED"
        assert w["trust"] == "UNVERIFIED"
        assert len(list_board(project="TEST")) == 1
        assert len(list_work(project="TEST")) == 1
        assert snapshot(project="TEST")["policy"]["privileged_external_actions"] == "DENY"
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def test_all_three_records_survive_fresh_connections(tmp_path, monkeypatch):
    from src.gcgw_workspace import append_note, list_notes
    monkeypatch.delenv("GCGW_DATABASE_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_ID", raising=False)
    monkeypatch.setenv("GCGW_DB_PATH", str(tmp_path / "persistent.db"))
    append_board("TEST", "PERSISTENCE", "board")
    append_work("TEST", "PERSISTENCE", "task", "WORKING", "work")
    append_note("TEST", "PERSISTENCE", "title", "note")
    assert list_board(project="PERSISTENCE")[0]["message"] == "board"
    assert list_work(project="PERSISTENCE")[0]["note"] == "work"
    assert list_notes(project="PERSISTENCE")[0]["body"] == "note"


def test_render_refuses_ephemeral_storage(tmp_path, monkeypatch):
    import pytest
    monkeypatch.delenv("GCGW_DATABASE_URL", raising=False)
    monkeypatch.delenv("GCGW_PERSISTENT_MOUNT", raising=False)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("GCGW_DB_PATH", str(tmp_path / "ephemeral.db"))
    with pytest.raises(RuntimeError, match="persistent storage"):
        append_board("TEST", "TEST", "must not acknowledge")


def test_postgres_integration(monkeypatch):
    import os
    import uuid
    import pytest
    from src.gcgw_workspace import append_note, list_notes
    url = os.getenv("GCGW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("integration database not configured")
    monkeypatch.setenv("GCGW_DATABASE_URL", url)
    project = "TEST-" + uuid.uuid4().hex
    b = append_board("TEST", project, "board")
    w = append_work("TEST", project, "task", "WORKING", "work")
    n = append_note("TEST", project, "title", "note")
    assert list_board(project=project) == [b]
    assert list_work(project=project) == [w]
    assert list_notes(project=project) == [n]
