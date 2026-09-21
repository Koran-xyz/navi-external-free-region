"""HTTP gateway for Navi External Free Region.

Endpoints:
- append-only Notion logging
- Multi-AI Chat v1 routing
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.multi_ai_router import route_and_call, shared_context
from src.notion_writer import NotionWriterError, append_record
from src.provider_clients import ProviderError, configured_providers, validate_provider_key
from src.robot_gateway import RobotError, execute_robot_job, robot_status

app = FastAPI(title="Navi External Free Region Gateway", version="0.4.0")
WEB_DIR = Path(__file__).resolve().parents[1] / "web"

allowed_origin = os.getenv("ALLOWED_ORIGIN", "").strip()
if allowed_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin],
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Authorization", "Content-Type", "X-OpenAI-API-Key", "X-Gemini-API-Key", "X-Copilot-API-Key"],
    )


class WorkRecord(BaseModel):
    record_name: str = Field(min_length=1, max_length=200)
    actor: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    result: str = Field(min_length=1, max_length=2000)
    next_action: str = Field(min_length=1, max_length=2000)
    status: str = Field(pattern="^(未着手|進行中|完了)$")
    source: str = Field(default="browser-chat / notion-writer", max_length=500)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    preferred_provider: str | None = Field(default=None, pattern="^(openai|gemini|copilot)$")
    verify: bool = False


class ProviderKeyCheckRequest(BaseModel):
    provider: str = Field(pattern="^(openai|gemini)$")
    api_key: str = Field(min_length=1, max_length=500)


class RobotJobRequest(BaseModel):
    robot_id: str = Field(min_length=1, max_length=100)
    meeting_id: str = Field(min_length=1, max_length=120)
    team_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=12000)
    target: dict = Field(default_factory=dict)
    dry_run: bool = False


def _authorize(authorization: str | None, env_name: str) -> None:
    expected = os.getenv(env_name, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"{env_name} is not configured")

    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/")
def index():
    return FileResponse(
        WEB_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.4.0"}


@app.get("/api/status")
def public_status():
    context = shared_context()
    return {
        "status": "ok",
        "providers": configured_providers(),
        "meta_rules_status": context.get("meta_rules_status", "unknown"),
        "project_id": context.get("project_id"),
    }


@app.get("/api/chat/providers")
def chat_providers(authorization: str | None = Header(default=None)):
    _authorize(authorization, "GATEWAY_CHAT_KEY")
    return {
        "providers": configured_providers(),
        "external_free_region": shared_context(),
    }


@app.post("/api/provider-key/validate")
async def provider_key_validate(
    request: ProviderKeyCheckRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization, "GATEWAY_CHAT_KEY")
    try:
        await validate_provider_key(request.provider, request.api_key)
        return {"valid": True, "provider": request.provider}
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
    x_openai_api_key: str | None = Header(default=None, alias="X-OpenAI-API-Key"),
    x_gemini_api_key: str | None = Header(default=None, alias="X-Gemini-API-Key"),
    x_copilot_api_key: str | None = Header(default=None, alias="X-Copilot-API-Key"),
):
    _authorize(authorization, "GATEWAY_CHAT_KEY")
    api_keys = {
        "openai": (x_openai_api_key or "").strip(),
        "gemini": (x_gemini_api_key or "").strip(),
        "copilot": (x_copilot_api_key or "").strip(),
    }
    try:
        return await route_and_call(
            message=request.message,
            preferred_provider=request.preferred_provider,
            verify=request.verify,
            api_keys=api_keys,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/robots/status")
def robots_status(authorization: str | None = Header(default=None)):
    _authorize(authorization, "ROBOT_GATEWAY_KEY")
    return {
        "mode": "append_only",
        "robots": robot_status(),
    }


@app.post("/api/robots/execute")
async def robot_execute(
    request: RobotJobRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization, "ROBOT_GATEWAY_KEY")
    try:
        return await execute_robot_job(request.model_dump())
    except RobotError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/api/notion/log")
def create_log(record: WorkRecord, authorization: str | None = Header(default=None)):
    _authorize(authorization, "GATEWAY_WRITE_KEY")
    try:
        return append_record(record.model_dump())
    except NotionWriterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
