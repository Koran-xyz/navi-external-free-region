"""Navi Multi-AI router v1.

Navi is the single front desk. The router selects an available AI, optionally
asks a second AI to verify the answer, then asks the primary AI to integrate the
two answers. External Free Region context is read locally from the canonical
repository files. Unfixed meta-rules are never treated as active rules.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.provider_clients import ProviderError, call_provider, configured_providers

ROOT = Path(__file__).resolve().parents[1]
META_RULES = ROOT / "META_RULES.md"
STATE_FILE = ROOT / "workspace" / "PROJECT_STATE.json"
HANDOFF_FILE = ROOT / "workspace" / "HANDOFF.json"

CODE_WORDS = ("python", "コード", "実装", "github", "api", "バグ", "プログラム")
RESEARCH_WORDS = ("調査", "比較", "検証", "研究", "検索", "根拠", "レビュー")
MICROSOFT_WORDS = ("copilot", "microsoft", "excel", "word", "powerpoint", "windows")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _meta_rules_fixed() -> bool:
    if not META_RULES.exists():
        return False
    text = META_RULES.read_text(encoding="utf-8")
    return "状態: 未固定" not in text and len(text.strip()) > 80


def shared_context() -> dict[str, Any]:
    state = _load_json(STATE_FILE)
    handoff = _load_json(HANDOFF_FILE)
    fixed = _meta_rules_fixed()
    return {
        "meta_rules_status": "fixed" if fixed else "unfixed",
        "meta_rules": META_RULES.read_text(encoding="utf-8") if fixed else None,
        "project_id": state.get("project_id"),
        "purpose": state.get("purpose"),
        "current_state": state.get("current_state"),
        "next_action": state.get("next_action"),
        "status": state.get("status"),
        "handoff_task": handoff.get("task"),
        "completion_rule": handoff.get("completion_rule"),
    }


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def choose_provider(
    message: str,
    preferred_provider: str | None = None,
    api_keys: dict[str, str] | None = None,
) -> str:
    available = configured_providers(api_keys)
    if preferred_provider:
        if preferred_provider not in available:
            raise ProviderError(f"unknown provider: {preferred_provider}")
        if not available[preferred_provider]:
            raise ProviderError(f"{preferred_provider} is not configured")
        return preferred_provider

    if _contains(message, MICROSOFT_WORDS) and available["copilot"]:
        return "copilot"
    if _contains(message, RESEARCH_WORDS) and available["gemini"]:
        return "gemini"
    if _contains(message, CODE_WORDS) and available["openai"]:
        return "openai"

    for candidate in ("openai", "gemini", "copilot"):
        if available[candidate]:
            return candidate
    raise ProviderError("no AI provider is configured")


def choose_verifier(primary: str, api_keys: dict[str, str] | None = None) -> str | None:
    available = configured_providers(api_keys)
    for candidate in ("gemini", "openai", "copilot"):
        if candidate != primary and available[candidate]:
            return candidate
    return None


def _system_prompt(context: dict[str, Any]) -> str:
    base = [
        "あなたはナビィ配下で作業するAIです。",
        "利用者の目的を優先し、未確認事項を完了扱いしないでください。",
        "削除・決済・公開・予約確定など不可逆または重要な外部操作は、人の承認なしに実行したと主張しないでください。",
        "与えられた共有状態を参考に、簡潔に回答してください。",
        f"共有目的: {context.get('purpose') or '未設定'}",
        f"現在地: {context.get('current_state') or '未設定'}",
        f"次作業: {context.get('next_action') or '未設定'}",
    ]
    if context.get("meta_rules_status") == "fixed":
        base.append("以下は固定済みメタルール原文です。勝手に言い換えて規則を変更しないでください。")
        base.append(context["meta_rules"])
    else:
        base.append("メタルール原文は未固定です。固定済みルールとして扱わないでください。")
    return "\n".join(base)


async def route_and_call(
    message: str,
    preferred_provider: str | None = None,
    verify: bool = False,
    api_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    api_keys = api_keys or {}
    context = shared_context()
    primary_name = choose_provider(message, preferred_provider, api_keys)
    system = _system_prompt(context)
    primary = await call_provider(primary_name, message, system, api_keys)

    result: dict[str, Any] = {
        "navi": {
            "selected_provider": primary_name,
            "verification_requested": verify,
            "external_free_region": context,
        },
        "answer": primary,
        "verification": None,
        "integrated_answer": primary["text"],
    }

    if not verify:
        return result

    verifier_name = choose_verifier(primary_name, api_keys)
    if not verifier_name:
        result["navi"]["verification_status"] = "skipped_no_second_provider"
        return result

    verification_prompt = (
        "次の回答を第三者として検証してください。\n"
        "一致している点、確認が必要な点、誤りの可能性がある点を分けてください。\n"
        "未確認の内容を事実として補わないでください。\n\n"
        f"利用者の依頼:\n{message}\n\n"
        f"一次回答:\n{primary['text']}"
    )
    verification = await call_provider(verifier_name, verification_prompt, system, api_keys)
    result["verification"] = verification

    integration_prompt = (
        "ナビィとして最終回答を統合してください。一次回答を優先せず、"
        "検証結果と照合し、食い違いは隠さず示してください。"
        "不明な点は不明としてください。\n\n"
        f"利用者の依頼:\n{message}\n\n"
        f"一次回答({primary_name}):\n{primary['text']}\n\n"
        f"検証回答({verifier_name}):\n{verification['text']}"
    )
    integrated = await call_provider(primary_name, integration_prompt, system, api_keys)
    result["integrated_answer"] = integrated["text"]
    result["navi"]["verification_status"] = "completed"
    result["navi"]["verifier"] = verifier_name
    return result
