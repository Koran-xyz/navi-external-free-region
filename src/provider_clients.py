"""AI provider adapters for Multi-AI Chat v1.

Secrets are read only from environment variables. No provider key is ever returned
to the browser.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


def configured_providers() -> dict[str, bool]:
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "copilot": bool(os.getenv("COPILOT_BRIDGE_URL", "").strip()),
    }


def _extract_openai_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    for item in data.get("output", []) or []:
        for part in item.get("content", []) or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if chunks:
        return "\n".join(chunks)
    raise ProviderError("OpenAI response did not contain text output")


def _extract_gemini_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for step in data.get("steps", []) or []:
        if step.get("type") != "model_output":
            continue
        for part in step.get("content", []) or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if chunks:
        return "\n".join(chunks)
    raise ProviderError("Gemini interaction did not contain text output")


async def call_openai(prompt: str, system: str) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ProviderError("OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
    payload = {
        "model": model,
        "input": prompt,
        "instructions": system,
        "store": False,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    if response.is_error:
        raise ProviderError(f"OpenAI API error: {response.status_code} {response.text[:500]}")
    data = response.json()
    return {
        "provider": "openai",
        "model": data.get("model", model),
        "text": _extract_openai_text(data),
        "request_id": data.get("id"),
    }


async def call_gemini(prompt: str, system: str) -> dict[str, Any]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ProviderError("GEMINI_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
    combined = f"{system}\n\n--- 利用者の依頼 ---\n{prompt}"
    payload = {
        "model": model,
        "input": combined,
        "store": False,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
        )
    if response.is_error:
        raise ProviderError(f"Gemini API error: {response.status_code} {response.text[:500]}")
    data = response.json()
    return {
        "provider": "gemini",
        "model": data.get("model", model),
        "text": _extract_gemini_text(data),
        "request_id": data.get("id"),
    }


async def call_copilot_bridge(prompt: str, system: str) -> dict[str, Any]:
    """Call a future/externally hosted Copilot adapter.

    Microsoft Copilot itself is not assumed to expose a generic chat endpoint.
    This adapter deliberately expects an operator-controlled bridge.
    """
    url = os.getenv("COPILOT_BRIDGE_URL", "").strip()
    if not url:
        raise ProviderError("COPILOT_BRIDGE_URL is not configured")

    key = os.getenv("COPILOT_BRIDGE_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json={"provider": "copilot", "input": prompt, "system": system},
        )
    if response.is_error:
        raise ProviderError(f"Copilot bridge error: {response.status_code} {response.text[:500]}")
    data = response.json()
    text = data.get("output_text") or data.get("text") or data.get("response")
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("Copilot bridge did not contain text output")
    return {
        "provider": "copilot",
        "model": data.get("model", "copilot-bridge"),
        "text": text.strip(),
        "request_id": data.get("id"),
    }


async def call_provider(provider: str, prompt: str, system: str) -> dict[str, Any]:
    if provider == "openai":
        return await call_openai(prompt, system)
    if provider == "gemini":
        return await call_gemini(prompt, system)
    if provider == "copilot":
        return await call_copilot_bridge(prompt, system)
    raise ProviderError(f"unsupported provider: {provider}")
