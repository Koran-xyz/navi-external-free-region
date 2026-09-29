"""AI provider adapters for Multi-AI Chat v1.

Provider keys can come from the server environment or, for a private device
session, from request-scoped overrides. Keys are never returned to the browser.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


def _key_from(overrides: dict[str, str] | None, name: str, env_name: str) -> str:
    if overrides:
        value = (overrides.get(name) or "").strip()
        if value:
            return value
    return os.getenv(env_name, "").strip()


def configured_providers(overrides: dict[str, str] | None = None) -> dict[str, bool]:
    return {
        "openai": bool(_key_from(overrides, "openai", "OPENAI_API_KEY")),
        "gemini": bool(_key_from(overrides, "gemini", "GEMINI_API_KEY")),
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
    """Extract text from Gemini GenerateContent or Interactions responses."""
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []

    # GenerateContent response shape.
    for candidate in data.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    # Interactions response shape (kept for backward compatibility).
    for step in data.get("steps", []) or []:
        if step.get("type") != "model_output":
            continue
        for part in step.get("content", []) or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    if chunks:
        return "\n".join(chunks)
    raise ProviderError("Gemini response did not contain text output")


async def validate_provider_key(provider: str, api_key: str) -> None:
    """Validate a provider key without generating chat content."""
    key = api_key.strip()
    if not key:
        raise ProviderError("API key is empty")

    async with httpx.AsyncClient(timeout=30.0) as client:
        if provider == "openai":
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        elif provider == "gemini":
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": key},
            )
        else:
            raise ProviderError(f"unsupported provider: {provider}")

    if response.is_error:
        if response.status_code in (400, 401, 403):
            raise ProviderError(f"{provider} API key is invalid")
        raise ProviderError(f"{provider} key validation failed: HTTP {response.status_code}")


async def call_openai(prompt: str, system: str, api_key: str | None = None) -> dict[str, Any]:
    key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
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


async def call_gemini(prompt: str, system: str, api_key: str | None = None) -> dict[str, Any]:
    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key:
        raise ProviderError("GEMINI_API_KEY is not configured")

    preferred = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
    fallbacks = [
        m.strip()
        for m in os.getenv(
            "GEMINI_FALLBACK_MODELS",
            "gemini-3.5-flash-lite,gemini-2.5-flash",
        ).split(",")
        if m.strip()
    ]

    models: list[str] = []
    for candidate in [preferred, *fallbacks]:
        if candidate and candidate not in models:
            models.append(candidate)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "system_instruction": {
            "parts": [{"text": system}],
        },
    }

    last_error = "unknown error"
    timeout = httpx.Timeout(connect=10.0, read=35.0, write=20.0, pool=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            try:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except httpx.TimeoutException:
                last_error = f"{model}: timeout"
                continue
            except httpx.RequestError as exc:
                last_error = f"{model}: network error ({exc.__class__.__name__})"
                continue

            if not response.is_error:
                data = response.json()
                return {
                    "provider": "gemini",
                    "model": model,
                    "text": _extract_gemini_text(data),
                    "request_id": response.headers.get("x-request-id"),
                }

            last_error = f"{model}: HTTP {response.status_code} {response.text[:300]}"

            # Retry another stable model for temporary capacity/rate-limit errors.
            if response.status_code in (429, 500, 502, 503, 504):
                continue

            # Model-not-found / invalid model can also fall back.
            if response.status_code == 404:
                continue

            break

    raise ProviderError(f"Gemini API error: {last_error}")


async def call_copilot_bridge(
    prompt: str,
    system: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    url = os.getenv("COPILOT_BRIDGE_URL", "").strip()
    if not url:
        raise ProviderError("COPILOT_BRIDGE_URL is not configured")

    key = (api_key or os.getenv("COPILOT_BRIDGE_KEY", "")).strip()
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


async def call_provider(
    provider: str,
    prompt: str,
    system: str,
    api_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    api_keys = api_keys or {}
    if provider == "openai":
        return await call_openai(prompt, system, api_keys.get("openai"))
    if provider == "gemini":
        return await call_gemini(prompt, system, api_keys.get("gemini"))
    if provider == "copilot":
        return await call_copilot_bridge(prompt, system, api_keys.get("copilot"))
    raise ProviderError(f"unsupported provider: {provider}")
