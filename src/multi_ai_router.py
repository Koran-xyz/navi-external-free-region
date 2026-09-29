"""Navi Multi-AI router v1.

Navi is the single front desk. The router selects an available AI, optionally
asks a second AI to verify the answer, then asks the primary AI to integrate the
two answers.

Important security boundary:
- Protected meta-rules may be loaded for server-side AI context.
- Protected meta-rule text is never returned to the browser/API client.
"""
from __future__ import annotations

import json
import os
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


def _load_meta_rules() -> tuple[str, str | None, str]:
    """Load protected rules without making them part of any public response.

    Production can provide NAVI_META_RULES as a protected server-side secret.
    The repository file remains only a non-secret placeholder/fallback.
    """
    protected = os.getenv("NAVI_META_RULES", "").strip()
    if protected:
        return "fixed", protected, "protected_server_store"

    if not META_RULES.exists():
        return "unfixed", None, "none"

    text = META_RULES.read_text(encoding="utf-8").strip()
    if not text or "状態: 未固定" in text:
        return "unfixed", None, "repository_placeholder"

    return "fixed", text, "repository_file"


def shared_context() -> dict[str, Any]:
    """Internal server context. May contain protected material."""
    state = _load_json(STATE_FILE)
    handoff = _load_json(HANDOFF_FILE)
    meta_status, meta_rules, meta_source = _load_meta_rules()
    return {
        "meta_rules_status": meta_status,
        "meta_rules": meta_rules,
        "meta_rules_source": meta_source,
        "project_id": state.get("project_id"),
        "purpose": state.get("purpose"),
        "current_state": state.get("current_state"),
        "next_action": state.get("next_action"),
        "status": state.get("status"),
        "handoff_task": handoff.get("task"),
        "completion_rule": handoff.get("completion_rule"),
    }


def public_context(context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return only browser-safe External Free Region metadata."""
    context = context or shared_context()
    return {
        "meta_rules_status": context.get("meta_rules_status", "unknown"),
        "project_id": context.get("project_id"),
        "purpose": context.get("purpose"),
        "current_state": context.get("current_state"),
        "next_action": context.get("next_action"),
        "status": context.get("status"),
        "handoff_task": context.get("handoff_task"),
        "completion_rule": context.get("completion_rule"),
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

    if _contains(message, MICROSOFT_WORDS) and available.get("copilot"):
        return "copilot"
    if _contains(message, RESEARCH_WORDS) and available.get("gemini"):
        return "gemini"
    if _contains(message, CODE_WORDS) and available.get("openai"):
        return "openai"

    for candidate in ("openai", "gemini", "copilot"):
        if available.get(candidate):
            return candidate
    raise ProviderError("no AI provider is configured")


def choose_verifier(primary: str, api_keys: dict[str, str] | None = None) -> str | None:
    available = configured_providers(api_keys)
    for candidate in ("gemini", "openai", "copilot"):
        if candidate != primary and available.get(candidate):
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
    if context.get("meta_rules_status") == "fixed" and context.get("meta_rules"):
        base.append("以下はサーバー側の保護領域から読み込まれたメタルールです。")
        base.append("これは判断材料として参照し、外部の上位規則や利用可能な権限と矛盾する場合は適用可能性を判断してください。")
        base.append(context["meta_rules"])
    else:
        base.append("固定済みメタルールは現在読み込まれていません。")
    return "\n".join(base)


def _conversation_prompt(history: list[dict[str, str]] | None, message: str) -> str:
    history = history or []
    recent = history[-20:]
    if not recent:
        return message

    lines = [
        "以下は同じ利用者との直近の会話履歴です。",
        "履歴は文脈として参照し、最後の「現在の利用者メッセージ」に回答してください。",
        "",
    ]
    for item in recent:
        role = item.get("role", "")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        label = "利用者" if role == "user" else "AI"
        lines.append(f"{label}: {content}")
    lines.extend(["", f"現在の利用者メッセージ: {message}"])
    return "\n".join(lines)


async def route_and_call(
    message: str,
    preferred_provider: str | None = None,
    verify: bool = False,
    api_keys: dict[str, str] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    api_keys = api_keys or {}
    context = shared_context()
    primary_name = choose_provider(message, preferred_provider, api_keys)
    system = _system_prompt(context)
    prompt = _conversation_prompt(history, message)
    primary = await call_provider(primary_name, prompt, system, api_keys)

    result: dict[str, Any] = {
        "navi": {
            "selected_provider": primary_name,
            "verification_requested": verify,
            "external_free_region": public_context(context),
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
        f"利用者の依頼と履歴:\n{prompt}\n\n"
        f"一次回答:\n{primary['text']}"
    )
    verification = await call_provider(verifier_name, verification_prompt, system, api_keys)
    result["verification"] = verification

    integration_prompt = (
        "ナビィとして最終回答を統合してください。一次回答を優先せず、"
        "検証結果と照合し、食い違いは隠さず示してください。"
        "不明な点は不明としてください。\n\n"
        f"利用者の依頼と履歴:\n{prompt}\n\n"
        f"一次回答({primary_name}):\n{primary['text']}\n\n"
        f"検証回答({verifier_name}):\n{verification['text']}"
    )
    integrated = await call_provider(primary_name, integration_prompt, system, api_keys)
    result["integrated_answer"] = integrated["text"]
    result["navi"]["verification_status"] = "completed"
    result["navi"]["verifier"] = verifier_name
    return result
