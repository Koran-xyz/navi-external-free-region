from language_gateway import route_request

def test_read_request_routes_to_read_only_robot() -> None:
    result = route_request({"actor": "test", "request": "現在地を確認したい"})
    assert result["decision"] == "route"
    assert result["robot"]["robot_id"] == "read_only"

def test_sensitive_request_is_blocked() -> None:
    result = route_request({"actor": "test", "request": "利用者名と住所を記録する"})
    assert result["decision"] == "blocked"

def test_external_action_requires_approval() -> None:
    result = route_request({"actor": "test", "request": "予約確定をする"})
    assert result["decision"] == "approval_required"
