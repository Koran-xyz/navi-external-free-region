"""Append-only external robot gateway for Navi.

The goal is to make external writes independent from any single AI platform.
Each AI submits the same job envelope; the server-side robot performs only the
allowed append operation and returns a normalized receipt.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
ROBOT_DIR = ROOT / "external_robots"
TEAM_REGISTRY = ROOT / "external_system" / "team_registry.json"

ROBOT_IDS = {
    "notion_page_append",
    "github_issue_comment",
    "google_docs_append",
}

_SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)(?:api[_ -]?key|access[_ -]?token|secret|password)\s*[:=]\s*[^\s]{8,}"),
)


class RobotError(RuntimeError):
    """Raised when a robot job cannot be safely executed."""


def load_robot_registry() -> dict[str, Any]:
    with (ROBOT_DIR / "robot_registry.json").open(encoding="utf-8") as f:
        return json.load(f)


def active_team_ids() -> set[str]:
    with TEAM_REGISTRY.open(encoding="utf-8") as f:
        registry = json.load(f)
    return {
        team["team_id"]
        for team in registry.get("teams", [])
        if team.get("status") == "active"
    }


def robot_status() -> dict[str, dict[str, Any]]:
    github_ready = bool(
        os.getenv("GITHUB_ROBOT_TOKEN", "").strip()
        or os.getenv("GITHUB_TOKEN", "").strip()
    )
    google_ready = bool(
        os.getenv("GOOGLE_DOCS_BRIDGE_URL", "").strip()
        or os.getenv("GOOGLE_DOCS_ACCESS_TOKEN", "").strip()
    )
    return {
        "notion_page_append": {
            "implemented": True,
            "configured": bool(os.getenv("NOTION_TOKEN", "").strip()),
            "mode": "append_only",
        },
        "github_issue_comment": {
            "implemented": True,
            "configured": github_ready,
            "mode": "append_only",
        },
        "google_docs_append": {
            "implemented": True,
            "configured": google_ready,
            "mode": "append_only",
        },
    }


def _contains_secret_like_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def validate_job(job: dict[str, Any]) -> None:
    robot_id = str(job.get("robot_id", "")).strip()
    meeting_id = str(job.get("meeting_id", "")).strip()
    team_id = str(job.get("team_id", "")).strip()
    content = str(job.get("content", "")).strip()
    target = job.get("target")

    if robot_id not in ROBOT_IDS:
        raise RobotError(f"unknown robot: {robot_id or 'empty'}")
    if not meeting_id:
        raise RobotError("meeting_id is required")
    if team_id not in active_team_ids():
        raise RobotError(f"unknown or inactive team: {team_id or 'empty'}")
    if not content:
        raise RobotError("content is required")
    if len(content) > 12000:
        raise RobotError("content is too long")
    if not isinstance(target, dict):
        raise RobotError("target must be an object")
    if _contains_secret_like_value(content):
        raise RobotError("secret-like value detected in robot content")

    if robot_id == "notion_page_append":
        if not str(target.get("page_id", "")).strip():
            raise RobotError("target.page_id is required")
    elif robot_id == "github_issue_comment":
        repo = str(target.get("repo", "")).strip()
        issue_number = target.get("issue_number")
        if "/" not in repo:
            raise RobotError("target.repo must be owner/name")
        if not isinstance(issue_number, int) or issue_number < 1:
            raise RobotError("target.issue_number must be a positive integer")
    elif robot_id == "google_docs_append":
        if not (
            str(target.get("document_id", "")).strip()
            or str(target.get("document_url", "")).strip()
        ):
            raise RobotError("target.document_id or target.document_url is required")


def _message(job: dict[str, Any]) -> str:
    return (
        f"[{job['meeting_id']}] {job['team_id']}\n"
        f"{str(job['content']).strip()}"
    )


def _split_text(text: str, size: int = 1800) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def _extract_google_document_id(target: dict[str, Any]) -> str:
    direct = str(target.get("document_id", "")).strip()
    if direct:
        return direct
    url = str(target.get("document_url", "")).strip()
    match = re.search(r"/document/d/([^/]+)", url)
    if not match:
        raise RobotError("could not extract Google document id")
    return match.group(1)


async def _notion_append(job: dict[str, Any]) -> dict[str, Any]:
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise RobotError("Notion robot is not configured")

    page_id = str(job["target"]["page_id"]).strip()
    children = []
    for chunk in _split_text(_message(job)):
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": chunk},
                        }
                    ]
                },
            }
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": os.getenv("NOTION_VERSION", "2025-09-03"),
        "Content-Type": "application/json",
    }
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.patch(url, headers=headers, json={"children": children})
    if response.status_code >= 400:
        raise RobotError(f"Notion robot failed with HTTP {response.status_code}")
    return {"target": "notion", "page_id": page_id}


async def _github_comment(job: dict[str, Any]) -> dict[str, Any]:
    token = (
        os.getenv("GITHUB_ROBOT_TOKEN", "").strip()
        or os.getenv("GITHUB_TOKEN", "").strip()
    )
    if not token:
        raise RobotError("GitHub robot is not configured")

    repo = str(job["target"]["repo"]).strip()
    issue_number = int(job["target"]["issue_number"])
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json={"body": _message(job)})
    if response.status_code >= 400:
        raise RobotError(f"GitHub robot failed with HTTP {response.status_code}")
    body = response.json()
    return {
        "target": "github",
        "repo": repo,
        "issue_number": issue_number,
        "comment_url": body.get("html_url"),
    }


async def _google_docs_append(job: dict[str, Any]) -> dict[str, Any]:
    document_id = _extract_google_document_id(job["target"])
    bridge_url = os.getenv("GOOGLE_DOCS_BRIDGE_URL", "").strip()
    content = "\n" + _message(job) + "\n"

    if bridge_url:
        headers = {"Content-Type": "application/json"}
        bridge_key = os.getenv("GOOGLE_DOCS_BRIDGE_KEY", "").strip()
        if bridge_key:
            headers["Authorization"] = f"Bearer {bridge_key}"
        payload = {
            "document_id": document_id,
            "content": content,
            "meeting_id": job["meeting_id"],
            "team_id": job["team_id"],
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(bridge_url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RobotError(
                f"Google Docs bridge failed with HTTP {response.status_code}"
            )
        return {"target": "google_docs", "document_id": document_id, "via": "bridge"}

    access_token = os.getenv("GOOGLE_DOCS_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RobotError("Google Docs robot is not configured")

    url = f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "requests": [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": content,
                }
            }
        ]
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        raise RobotError(f"Google Docs robot failed with HTTP {response.status_code}")
    return {"target": "google_docs", "document_id": document_id, "via": "direct"}


async def execute_robot_job(job: dict[str, Any]) -> dict[str, Any]:
    validate_job(job)
    job_id = f"ROBOT-{uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    if bool(job.get("dry_run")):
        return {
            "ok": True,
            "job_id": job_id,
            "robot_id": job["robot_id"],
            "meeting_id": job["meeting_id"],
            "team_id": job["team_id"],
            "state": "dry_run",
            "executed_at": now,
            "external": None,
        }

    statuses = robot_status()
    if not statuses[job["robot_id"]]["configured"]:
        raise RobotError(f"{job['robot_id']} is not configured")

    if job["robot_id"] == "notion_page_append":
        external = await _notion_append(job)
    elif job["robot_id"] == "github_issue_comment":
        external = await _github_comment(job)
    else:
        external = await _google_docs_append(job)

    return {
        "ok": True,
        "job_id": job_id,
        "robot_id": job["robot_id"],
        "meeting_id": job["meeting_id"],
        "team_id": job["team_id"],
        "state": "completed",
        "executed_at": now,
        "external": external,
    }
