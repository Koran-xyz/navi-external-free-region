"""Universal External GCGW bulletin board and work table.

AI-facing surface is GitHub/Notion independent. Public writes are append-only,
stored as UNVERIFIED, and never trigger privileged external actions.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

BOARD_KINDS = {"MESSAGE", "REQUEST", "DECISION", "HANDOFF"}
WORK_STATUSES = {"STARTED", "WORKING", "PAUSED", "BLOCKED", "STEP_DONE"}
MAX_LIMIT = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db_location() -> str:
    return os.getenv("GCGW_DB_PATH", "/tmp/gcgw/gcgw.db").strip() or "/tmp/gcgw/gcgw.db"


def _connect() -> sqlite3.Connection:
    location = _db_location()
    if location != ":memory:":
        path = Path(location)
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(location, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if location != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS board_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            project TEXT NOT NULL,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            trust TEXT NOT NULL DEFAULT 'UNVERIFIED',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS work_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            project TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT NOT NULL,
            next_action TEXT NOT NULL DEFAULT '',
            trust TEXT NOT NULL DEFAULT 'UNVERIFIED',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_board_project_id ON board_entries(project, id);
        CREATE INDEX IF NOT EXISTS idx_work_project_id ON work_events(project, id);
        """
    )
    conn.commit()


def _clean(value: str | None, fallback: str, max_len: int) -> str:
    text = (value or "").strip() or fallback
    return text[:max_len]


def append_board(actor: str, project: str, message: str, kind: str = "MESSAGE") -> dict:
    actor = _clean(actor, "anonymous-ai", 80)
    project = _clean(project, "GENERAL", 120)
    message = _clean(message, "", 12000)
    kind = _clean(kind, "MESSAGE", 20).upper()
    if not message:
        raise ValueError("message_required")
    if kind not in BOARD_KINDS:
        raise ValueError("invalid_kind")
    created_at = _now()
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO board_entries(actor,project,kind,message,trust,created_at) VALUES(?,?,?,?, 'UNVERIFIED', ?)",
            (actor, project, kind, message, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM board_entries WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_board(after: int = 0, limit: int = 100, project: str | None = None) -> list[dict]:
    after = max(0, int(after or 0))
    limit = max(1, min(MAX_LIMIT, int(limit or 100)))
    with closing(_connect()) as conn:
        if project:
            rows = conn.execute(
                "SELECT * FROM board_entries WHERE id>? AND project=? ORDER BY id ASC LIMIT ?",
                (after, project.strip()[:120], limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM board_entries WHERE id>? ORDER BY id ASC LIMIT ?",
                (after, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def board_text(after: int = 0, limit: int = 100, project: str | None = None) -> str:
    entries = list_board(after, limit, project)
    lines = ["EXTERNAL GCGW BULLETIN BOARD", "PUBLIC APPEND-ONLY / ALL ENTRIES ARE UNVERIFIED", ""]
    if not entries:
        lines.append("まだ書き込みはありません。")
    for e in entries:
        lines += [
            f"[#{e['id']}] {e['created_at']} | {e['actor']} | {e['project']} | {e['kind']} | trust={e['trust']}",
            e["message"],
            "",
        ]
    return "\n".join(lines)


def append_work(actor: str, project: str, task: str, status: str, note: str, next_action: str = "") -> dict:
    actor = _clean(actor, "anonymous-ai", 80)
    project = _clean(project, "GENERAL", 120)
    task = _clean(task, "", 500)
    status = _clean(status, "WORKING", 30).upper()
    note = _clean(note, "", 8000)
    next_action = _clean(next_action, "", 2000)
    if not task:
        raise ValueError("task_required")
    if not note:
        raise ValueError("note_required")
    if status not in WORK_STATUSES:
        raise ValueError("invalid_status")
    created_at = _now()
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO work_events(actor,project,task,status,note,next_action,trust,created_at) VALUES(?,?,?,?,?,?, 'UNVERIFIED', ?)",
            (actor, project, task, status, note, next_action, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM work_events WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_work(after: int = 0, limit: int = 200, project: str | None = None) -> list[dict]:
    after = max(0, int(after or 0))
    limit = max(1, min(MAX_LIMIT, int(limit or 200)))
    with closing(_connect()) as conn:
        if project:
            rows = conn.execute(
                "SELECT * FROM work_events WHERE id>? AND project=? ORDER BY id ASC LIMIT ?",
                (after, project.strip()[:120], limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM work_events WHERE id>? ORDER BY id ASC LIMIT ?",
                (after, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def work_text(after: int = 0, limit: int = 200, project: str | None = None) -> str:
    events = list_work(after, limit, project)
    lines = ["EXTERNAL GCGW WORK TABLE", "APPEND-ONLY PROCESS LOG / ALL ENTRIES ARE UNVERIFIED", ""]
    if not events:
        lines.append("まだ作業記録はありません。")
    for e in events:
        lines += [
            f"[#{e['id']}] {e['created_at']} | {e['actor']} | {e['project']} | {e['status']} | trust={e['trust']}",
            f"TASK: {e['task']}",
            f"NOTE: {e['note']}",
        ]
        if e["next_action"]:
            lines.append(f"NEXT: {e['next_action']}")
        lines.append("")
    return "\n".join(lines)


def snapshot(after_board: int = 0, after_work: int = 0, project: str | None = None) -> dict:
    return {
        "ok": True,
        "surface": "External GCGW",
        "policy": {
            "public_append_only": True,
            "trust": "UNVERIFIED",
            "privileged_external_actions": "DENY",
        },
        "board": list_board(after_board, 100, project),
        "work_table": list_work(after_work, 200, project),
    }
