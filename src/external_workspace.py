"""Navi External Free Region v0.1

自然言語のメタルールを勝手に変えず、読込確認・状態確認・作業記録を
どのPython環境でも同じ型で扱う最小ランタイム。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
META_RULES = ROOT / "META_RULES.md"
STATE_FILE = ROOT / "workspace" / "PROJECT_STATE.json"
HANDOFF_FILE = ROOT / "workspace" / "HANDOFF.json"
LOG_FILE = ROOT / "logs" / "event_log.jsonl"

REQUIRED_STATE = {
    "project_id",
    "title",
    "purpose",
    "current_state",
    "next_action",
    "assigned_roles",
    "status",
    "updated_at",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def meta_rules_are_fixed() -> bool:
    text = META_RULES.read_text(encoding="utf-8")
    return "状態: 未固定" not in text and len(text.strip()) > 80


def validate() -> list[str]:
    errors: list[str] = []
    for path in (META_RULES, STATE_FILE, HANDOFF_FILE):
        if not path.exists():
            errors.append(f"不足: {path.relative_to(ROOT)}")

    if STATE_FILE.exists():
        state = load_json(STATE_FILE)
        missing = REQUIRED_STATE - set(state)
        if missing:
            errors.append(f"PROJECT_STATE.json の不足項目: {', '.join(sorted(missing))}")

    if META_RULES.exists() and not meta_rules_are_fixed():
        errors.append("停止: META_RULES.md の正式原文が未固定")

    return errors


def record(kind: str, actor: str, content: str) -> None:
    errors = validate()
    if errors:
        raise RuntimeError("\n".join(errors))

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "actor": actor,
        "content": content,
        "project_id": load_json(STATE_FILE)["project_id"],
    }
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def show_status() -> None:
    state = load_json(STATE_FILE)
    print(f"目的: {state['purpose']}")
    print(f"現在地: {state['current_state']}")
    print(f"次作業: {state['next_action']}")
    print(f"状態: {state['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate")
    subcommands.add_parser("status")
    report = subcommands.add_parser("report")
    report.add_argument("--actor", required=True)
    report.add_argument("--kind", default="作業報告")
    report.add_argument("--content", required=True)
    args = parser.parse_args()

    if args.command == "validate":
        errors = validate()
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        print("確認済み: 外部自由領域の最小構成は有効です。")
    elif args.command == "status":
        show_status()
    else:
        record(args.kind, args.actor, args.content)
        print("記録しました。")


if __name__ == "__main__":
    main()
