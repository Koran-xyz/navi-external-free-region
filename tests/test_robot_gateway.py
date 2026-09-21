import asyncio
import os
from unittest.mock import patch

import pytest

from src.robot_gateway import (
    RobotError,
    execute_robot_job,
    robot_status,
    validate_job,
)


def base_job():
    return {
        "robot_id": "notion_page_append",
        "meeting_id": "MEETING-TEST",
        "team_id": "goten_team",
        "content": "テスト回答",
        "target": {"page_id": "page-123"},
        "dry_run": True,
    }


def test_robot_status_has_three_append_robots():
    with patch.dict(os.environ, {}, clear=True):
        status = robot_status()
    assert set(status) == {
        "notion_page_append",
        "github_issue_comment",
        "google_docs_append",
    }
    assert all(item["mode"] == "append_only" for item in status.values())


def test_unknown_team_is_rejected():
    job = base_job()
    job["team_id"] = "unknown_team"
    with pytest.raises(RobotError):
        validate_job(job)


def test_secret_like_value_is_rejected():
    job = base_job()
    job["content"] = "api_key=sk-proj-abcdefghijklmnop1234567890"
    with pytest.raises(RobotError):
        validate_job(job)


def test_github_target_requires_issue_number():
    job = base_job()
    job["robot_id"] = "github_issue_comment"
    job["target"] = {"repo": "Koran-xyz/navi-external-free-region"}
    with pytest.raises(RobotError):
        validate_job(job)


def test_dry_run_returns_receipt_without_credentials():
    receipt = asyncio.run(execute_robot_job(base_job()))
    assert receipt["ok"] is True
    assert receipt["state"] == "dry_run"
    assert receipt["robot_id"] == "notion_page_append"
    assert receipt["external"] is None
