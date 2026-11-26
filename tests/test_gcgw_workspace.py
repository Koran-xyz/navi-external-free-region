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
