from src.external_system_region import (
    active_team_ids,
    finalize_meeting,
    meeting_ready_for_admin,
    new_meeting,
    record_team_answer,
)


def test_team_registry_has_three_active_teams():
    assert active_team_ids() == [
        "goten_team",
        "maria_assistant_team",
        "eden_team",
    ]


def test_meeting_moves_to_admin_review_after_all_team_answers():
    meeting = new_meeting("共通の議題を検討する", meeting_id="MEETING-TEST")
    for team in meeting["participants"]:
        meeting = record_team_answer(meeting, team, f"{team}の回答")

    assert meeting_ready_for_admin(meeting) is True
    assert meeting["status"] == "admin_review"


def test_finalize_meeting():
    meeting = new_meeting("議題", participants=["goten_team"], meeting_id="MEETING-ONE")
    meeting = record_team_answer(meeting, "goten_team", "回答")
    meeting = finalize_meeting(meeting, "整理", "最終結果", "次の作業")

    assert meeting["status"] == "completed"
    assert meeting["final_result"] == "最終結果"


def test_unknown_team_is_rejected():
    try:
        new_meeting("議題", participants=["unknown_team"])
    except ValueError as exc:
        assert "unknown or inactive team" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")
