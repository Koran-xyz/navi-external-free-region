"""External System Region core.

This module keeps the machine-readable meeting packet independent from any
single AI platform. Notion/Docs/GitHub adapters can read and write this common
shape later without changing the team protocol.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_SYSTEM_DIR = ROOT / "external_system"


def load_team_registry() -> dict:
    with (EXTERNAL_SYSTEM_DIR / "team_registry.json").open(encoding="utf-8") as f:
        return json.load(f)


def active_team_ids() -> list[str]:
    registry = load_team_registry()
    return [team["team_id"] for team in registry["teams"] if team.get("status") == "active"]


def new_meeting(
    user_request: str,
    mode: str = "integrated",
    participants: list[str] | None = None,
    meeting_id: str | None = None,
) -> dict:
    if mode not in {"integrated", "parallel"}:
        raise ValueError("mode must be integrated or parallel")
    if not user_request.strip():
        raise ValueError("user_request is required")

    active = active_team_ids()
    selected = participants or active
    unknown = [team for team in selected if team not in active]
    if unknown:
        raise ValueError(f"unknown or inactive team: {', '.join(unknown)}")

    return {
        "meeting_id": meeting_id or f"MEETING-{uuid4().hex[:8].upper()}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_request": user_request.strip(),
        "mode": mode,
        "participants": selected,
        "status": "received",
        "team_answers": {team: None for team in active},
        "discussion_log": [],
        "admin_summary": None,
        "final_result": None,
        "next_action": None,
    }


def record_team_answer(meeting: dict, team_id: str, answer: str) -> dict:
    if team_id not in meeting.get("participants", []):
        raise ValueError("team is not a participant")
    if not answer.strip():
        raise ValueError("answer is required")

    updated = deepcopy(meeting)
    updated["team_answers"][team_id] = answer.strip()
    updated["discussion_log"].append(
        {
            "speaker": team_id,
            "type": "team_answer",
            "content": answer.strip(),
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    updated["status"] = "discussing"
    if meeting_ready_for_admin(updated):
        updated["status"] = "admin_review"
    return updated


def meeting_ready_for_admin(meeting: dict) -> bool:
    answers = meeting.get("team_answers", {})
    return all(bool(answers.get(team)) for team in meeting.get("participants", []))


def finalize_meeting(
    meeting: dict,
    admin_summary: str,
    final_result: str,
    next_action: str | None = None,
) -> dict:
    if not admin_summary.strip() or not final_result.strip():
        raise ValueError("admin_summary and final_result are required")

    updated = deepcopy(meeting)
    updated["admin_summary"] = admin_summary.strip()
    updated["final_result"] = final_result.strip()
    updated["next_action"] = (next_action or "").strip() or None
    updated["status"] = "completed"
    return updated
