"""Notion append-only writer for the external free region.

This module creates NEW pages only. It never edits or deletes existing records.
Secrets are read only from environment variables.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = os.getenv("NOTION_VERSION", "2025-09-03")
DEFAULT_DATA_SOURCE_ID = "b3bd8666-728d-4a94-8d97-a0d28c686899"

REQUIRED_FIELDS = (
    "record_name",
    "actor",
    "summary",
    "evidence",
    "result",
    "next_action",
    "status",
)
ALLOWED_STATUS = {"未着手", "進行中", "完了"}
SENSITIVE_WORDS = (
    "パスワード",
    "APIキー",
    "認証情報",
    "生GPS",
    "住所",
    "利用者名",
    "患者名",
)


class NotionWriterError(RuntimeError):
    """Raised when a record cannot be safely written."""


def validate_record(record: dict[str, Any]) -> None:
    missing = [name for name in REQUIRED_FIELDS if not str(record.get(name, "")).strip()]
    if missing:
        raise NotionWriterError(f"必須項目が不足しています: {', '.join(missing)}")

    if record["status"] not in ALLOWED_STATUS:
        raise NotionWriterError("status は 未着手 / 進行中 / 完了 のいずれかです")

    if record["status"] == "完了" and not str(record["evidence"]).strip():
        raise NotionWriterError("完了には根拠・確認結果が必要です")

    combined = " ".join(str(record.get(name, "")) for name in REQUIRED_FIELDS)
    found = [word for word in SENSITIVE_WORDS if word in combined]
    if found:
        raise NotionWriterError(
            "共通記録庫へ直接入れない情報が含まれる可能性があります: "
            + ", ".join(found)
        )


def _rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def build_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Map the common work-record contract to the current Notion schema."""
    validate_record(record)

    data_source_id = os.getenv("NOTION_DATA_SOURCE_ID", DEFAULT_DATA_SOURCE_ID)

    return {
        "parent": {
            "type": "data_source_id",
            "data_source_id": data_source_id,
        },
        "properties": {
            "記録名": _title(str(record["record_name"])),
            "事務所・領域": {"select": {"name": "共通"}},
            "作業分担": {"select": {"name": "AI"}},
            "依頼・概要": _rich_text(str(record["summary"])),
            "参照元": _rich_text(str(record.get("source", "browser-chat / notion-writer"))),
            "参照範囲": {"select": {"name": "全社共通"}},
            "外部へ渡す可否": {"select": {"name": "承認後のみ"}},
            "担当": _rich_text(str(record["actor"])),
            "根拠・確認結果": _rich_text(str(record["evidence"])),
            "業務区分": {"select": {"name": "実績記録"}},
            "次の作業": _rich_text(str(record["next_action"])),
            "状態": {"status": {"name": str(record["status"])}},
            "結果": _rich_text(str(record["result"])),
        },
    }


def append_record(record: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    """Create one new Notion record and return a compact result."""
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionWriterError("NOTION_TOKEN が設定されていません")

    payload = build_payload(record)
    request = Request(
        NOTION_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise NotionWriterError(f"Notion API error {exc.code}: {detail}") from exc
    except URLError as exc:
        raise NotionWriterError(f"Notion APIへ接続できません: {exc.reason}") from exc

    return {
        "ok": True,
        "page_id": body.get("id"),
        "url": body.get("url"),
        "record_name": record["record_name"],
    }


if __name__ == "__main__":
    import sys

    incoming = json.load(sys.stdin)
    print(json.dumps(append_record(incoming), ensure_ascii=False, indent=2))
