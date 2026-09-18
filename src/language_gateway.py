"""外部自由領域の言語窓口 v0.1。

自然言語の依頼を受け取り、固定ルールを読み、
実行せずに適切なロボットへ渡すための受付パケットを返す。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "rules" / "LANGUAGE_GATEWAY_RULES.md"
REGISTRY_FILE = ROOT / "agents" / "robot_registry.json"

SENSITIVE_WORDS = ("住所", "GPS", "位置情報", "利用者名", "患者名", "パスワード", "APIキー", "認証情報")
APPROVAL_WORDS = ("削除", "上書き", "外部送信", "予約確定", "決済", "公開")
READ_WORDS = ("読む", "読み出し", "確認", "現在地", "状態", "次の作業")
WRITE_WORDS = ("記録", "追記", "報告", "書き込み", "ログ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def route_request(request: dict[str, str]) -> dict[str, Any]:
    text = request.get("request", "").strip()
    actor = request.get("actor", "").strip()

    if not text or not actor:
        raise ValueError("actor と request は必須です")

    # Python は固定ルールを必ず読み込む。ルール本文の解釈は人とAIが管理する。
    rules_loaded = RULES_FILE.exists() and bool(RULES_FILE.read_text(encoding="utf-8").strip())
    robots = load_json(REGISTRY_FILE)["robots"]

    packet: dict[str, Any] = {
        "actor": actor,
        "original_request": text,
        "rules_loaded": rules_loaded,
        "execution": "not_started",
        "approval_required": False,
        "robot": None,
        "required_fields": [],
        "reason": "",
    }

    if contains_any(text, SENSITIVE_WORDS):
        packet.update(
            decision="blocked",
            reason="共通記録庫へ入れられない情報が含まれる可能性があります",
            required_fields=["匿名化した要約"],
        )
    elif contains_any(text, APPROVAL_WORDS):
        packet.update(
            decision="approval_required",
            approval_required=True,
            reason="削除・外部送信・確定操作は人の承認が必要です",
            required_fields=["承認者", "承認理由"],
        )
    elif contains_any(text, READ_WORDS):
        robot = next(item for item in robots if item["robot_id"] == "read_only")
        packet.update(
            decision="route",
            robot=robot,
            reason="現在地・ルール・名札の参照依頼として受け付けました",
        )
    elif contains_any(text, WRITE_WORDS):
        robot = next(item for item in robots if item["robot_id"] == "write_only")
        packet.update(
            decision="route",
            robot=robot,
            reason="新規の作業報告として受け付けました",
            required_fields=robot["required_fields"],
        )
    else:
        packet.update(
            decision="needs_clarification",
            reason="読み出し・新規記録・承認待ちのどれかを指定してください",
            required_fields=["目的", "希望するロボット"],
        )
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", required=True)
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    print(json.dumps(route_request(vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
