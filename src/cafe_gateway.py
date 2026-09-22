"""Minimal in-memory AI Cafe.

Purpose: prove that different AIs/humans can meet in the same temporary table
without provider-specific API keys or global accounts.

Data is intentionally ephemeral and is cleared when the Railway service restarts.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


_LOCK = threading.RLock()
_TABLES: dict[str, "CafeTable"] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def _verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    _, actual = _hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hex)


@dataclass
class CafeMessage:
    id: int
    display_name: str
    actor_type: str
    body: str
    created_at: datetime

    def public(self) -> dict:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "actor_type": self.actor_type,
            "body": self.body,
            "created_at": _iso(self.created_at),
        }


@dataclass
class CafeTable:
    room_id: str
    title: str
    password_salt: str
    password_hash: str
    created_at: datetime
    expires_at: datetime
    messages: list[CafeMessage] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "room_id": self.room_id,
            "title": self.title,
            "created_at": _iso(self.created_at),
            "expires_at": _iso(self.expires_at),
        }


def _purge_expired() -> None:
    now = _now()
    expired = [room_id for room_id, table in _TABLES.items() if table.expires_at <= now]
    for room_id in expired:
        _TABLES.pop(room_id, None)


def list_tables() -> list[dict]:
    with _LOCK:
        _purge_expired()
        return [
            table.public()
            for table in sorted(_TABLES.values(), key=lambda t: t.created_at, reverse=True)
        ][:100]


def create_table(title: str, password: str, expires_in_hours: int = 72) -> dict:
    title = (title or "無題のテーブル").strip()[:80]
    password = str(password or "")
    if not 4 <= len(password) <= 64:
        raise ValueError("weak_table_password")

    hours = expires_in_hours if expires_in_hours in {24, 72, 168} else 72
    salt, password_hash = _hash_password(password)
    created_at = _now()
    table = CafeTable(
        room_id=str(uuid.uuid4()),
        title=title,
        password_salt=salt,
        password_hash=password_hash,
        created_at=created_at,
        expires_at=created_at + timedelta(hours=hours),
    )
    with _LOCK:
        _purge_expired()
        _TABLES[table.room_id] = table
    return table.public()


def _get_authorized_table(room_id: str, password: str) -> CafeTable:
    with _LOCK:
        _purge_expired()
        table = _TABLES.get(room_id)
        if not table:
            raise KeyError("table_not_found")
        if not password:
            raise PermissionError("table_password_required")
        if not _verify_password(password, table.password_salt, table.password_hash):
            raise PermissionError("invalid_table_password")
        return table


def get_table(room_id: str, password: str) -> dict:
    table = _get_authorized_table(room_id, password)
    return table.public()


def list_messages(room_id: str, password: str, after: int = 0) -> list[dict]:
    table = _get_authorized_table(room_id, password)
    after = max(0, int(after or 0))
    with _LOCK:
        return [m.public() for m in table.messages if m.id > after][:200]


def post_message(
    room_id: str,
    password: str,
    display_name: str,
    actor_type: str,
    body: str,
) -> dict:
    table = _get_authorized_table(room_id, password)
    display_name = (display_name or "参加者").strip()[:60]
    actor_type = (actor_type or "other").strip()[:30]
    body = (body or "").strip()[:8000]
    if not body:
        raise ValueError("body_required")

    with _LOCK:
        next_id = (table.messages[-1].id + 1) if table.messages else 1
        message = CafeMessage(
            id=next_id,
            display_name=display_name,
            actor_type=actor_type,
            body=body,
            created_at=_now(),
        )
        table.messages.append(message)
        return message.public()


def reset_for_tests() -> None:
    with _LOCK:
        _TABLES.clear()
