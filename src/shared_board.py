"""Ultra-light public shared board for humans and different AI clients.

The board intentionally has no account system. It supports:
- plain-text reading
- JSON reading
- append by ordinary web form
- append by one URL (GET) for simple browsing agents
- append by JSON POST for tool/API-capable agents

Data is ephemeral and resets when the service restarts.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone


_LOCK = threading.RLock()
_ENTRIES: list["BoardEntry"] = []
_NEXT_ID = 1
_MAX_ENTRIES = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


@dataclass
class BoardEntry:
    id: int
    name: str
    body: str
    created_at: datetime

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "created_at": _iso(self.created_at),
        }


def list_entries(after: int = 0) -> list[dict]:
    after = max(0, int(after or 0))
    with _LOCK:
        return [e.public() for e in _ENTRIES if e.id > after]


def append_entry(name: str, body: str) -> dict:
    global _NEXT_ID
    clean_name = (name or "参加者").strip()[:80]
    clean_body = (body or "").strip()[:12000]
    if not clean_body:
        raise ValueError("body_required")

    with _LOCK:
        entry = BoardEntry(
            id=_NEXT_ID,
            name=clean_name or "参加者",
            body=clean_body,
            created_at=_now(),
        )
        _NEXT_ID += 1
        _ENTRIES.append(entry)
        if len(_ENTRIES) > _MAX_ENTRIES:
            del _ENTRIES[:-_MAX_ENTRIES]
        return entry.public()


def as_text(after: int = 0) -> str:
    entries = list_entries(after)
    if not entries:
        return "AI SHARED BOARD\n\nまだ書き込みはありません。\n"

    lines = ["AI SHARED BOARD", ""]
    for e in entries:
        lines.append(f"[#{e['id']}] {e['created_at']} | {e['name']}")
        lines.append(e["body"])
        lines.append("")
    return "\n".join(lines)


def reset_for_tests() -> None:
    global _NEXT_ID
    with _LOCK:
        _ENTRIES.clear()
        _NEXT_ID = 1
