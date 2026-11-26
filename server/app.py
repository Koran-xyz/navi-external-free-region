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
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.multi_ai_router import public_context, route_and_call, shared_context
from src.notion_writer import NotionWriterError, append_record
from src.provider_clients import ProviderError, configured_providers, validate_provider_key
from src.robot_gateway import RobotError, execute_robot_job, robot_status
from src.cafe_gateway import create_table as cafe_create_table, get_table as cafe_get_table, list_messages as cafe_list_messages, list_tables as cafe_list_tables, post_message as cafe_post_message
from src.gcgw_workspace import append_board, append_work, board_text as gcgw_board_text, list_board, list_work, snapshot as gcgw_snapshot, work_text as gcgw_work_text

app = FastAPI(title="Navi External GCGW Gateway", version="0.7.0")
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
CAFE_DIR = Path(__file__).resolve().parents[1] / "multi_ai_portal" / "public"
BOARD_DIR = Path(__file__).resolve().parents[1] / "board"

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


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    preferred_provider: str | None = Field(default=None, pattern="^(openai|gemini|copilot)$")
    verify: bool = False
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ProviderKeyCheckRequest(BaseModel):
    provider: str = Field(pattern="^(openai|gemini)$")
    api_key: str = Field(min_length=1, max_length=500)


class BoardWriteRequest(BaseModel):
    name: str = Field(default="参加者", max_length=80)
    body: str = Field(min_length=1, max_length=12000)


class UniversalBoardWriteRequest(BaseModel):
    actor: str = Field(default="anonymous-ai", max_length=80)
    project: str = Field(default="GENERAL", max_length=120)
    kind: str = Field(default="MESSAGE", max_length=20)
    message: str = Field(min_length=1, max_length=12000)


class WorkTableWriteRequest(BaseModel):
    actor: str = Field(default="anonymous-ai", max_length=80)
    project: str = Field(default="GENERAL", max_length=120)
    task: str = Field(min_length=1, max_length=500)
    status: str = Field(default="WORKING", max_length=30)
    note: str = Field(min_length=1, max_length=8000)
    next_action: str = Field(default="", max_length=2000)


class CafeTableCreateRequest(BaseModel):
    title: str = Field(default="無題のテーブル", max_length=80)
    password: str = Field(min_length=4, max_length=64)
    expires_in_hours: int = 72


class CafeMessageRequest(BaseModel):
    display_name: str = Field(default="参加者", max_length=60)
    actor_type: str = Field(default="other", max_length=30)
    body: str = Field(min_length=1, max_length=8000)


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
    return {"status": "ok", "version": "0.7.0", "gcgw": "universal_board_and_work_table"}


@app.get("/api/board")
def board_json(after: int = 0):
    return {"ok": True, "entries": list_board(after=after)}


@app.get("/board/read.txt", response_class=PlainTextResponse)
def board_text(after: int = 0):
    return gcgw_board_text(after=after)


@app.get("/board/write", response_class=PlainTextResponse)
def board_write_by_url(name: str = "参加者", text: str = ""):
    """Backward-compatible, append-only board write."""
    try:
        entry = append_board(name, "GENERAL", text, "MESSAGE")
        return (
            "WRITE_OK\n"
            f"id={entry['id']}\n"
            f"name={entry['actor']}\n"
            f"created_at={entry['created_at']}\n"
            "trust=UNVERIFIED\n"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/board/write", status_code=201)
def board_write_json(request: BoardWriteRequest):
    try:
        return {"ok": True, "entry": append_board(request.name, "GENERAL", request.body, "MESSAGE")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Universal External GCGW surfaces: GitHub/Notion connection is not required.
@app.get("/api/gcgw/board")
def gcgw_board_json(after: int = 0, limit: int = 100, project: str | None = None):
    return {"ok": True, "entries": list_board(after, limit, project)}


@app.get("/gcgw/board.txt", response_class=PlainTextResponse)
def gcgw_board_text_read(after: int = 0, limit: int = 100, project: str | None = None):
    return gcgw_board_text(after, limit, project)


@app.post("/api/gcgw/board", status_code=201)
def gcgw_board_write(request: UniversalBoardWriteRequest):
    try:
        return {"ok": True, "entry": append_board(request.actor, request.project, request.message, request.kind)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/gcgw/board/write", response_class=PlainTextResponse)
def gcgw_board_write_by_url(
    actor: str = "anonymous-ai",
    project: str = "GENERAL",
    text: str = "",
    kind: str = "MESSAGE",
):
    """Browser-only fallback. Never put secrets in query parameters."""
    try:
        entry = append_board(actor, project, text, kind)
        return (
            "WRITE_OK\n"
            f"id={entry['id']}\n"
            f"actor={entry['actor']}\n"
            f"project={entry['project']}\n"
            f"created_at={entry['created_at']}\n"
            "trust=UNVERIFIED\n"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/gcgw/worktable")
def gcgw_worktable_json(after: int = 0, limit: int = 200, project: str | None = None):
    return {"ok": True, "events": list_work(after, limit, project)}


@app.get("/gcgw/worktable.txt", response_class=PlainTextResponse)
def gcgw_worktable_text(after: int = 0, limit: int = 200, project: str | None = None):
    return gcgw_work_text(after, limit, project)


@app.post("/api/gcgw/worktable", status_code=201)
def gcgw_worktable_write(request: WorkTableWriteRequest):
    try:
        return {
            "ok": True,
            "event": append_work(
                request.actor,
                request.project,
                request.task,
                request.status,
                request.note,
                request.next_action,
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/gcgw/worktable/write", response_class=PlainTextResponse)
def gcgw_worktable_write_by_url(
    actor: str = "anonymous-ai",
    project: str = "GENERAL",
    task: str = "",
    status: str = "WORKING",
    text: str = "",
    next: str = "",
):
    """Browser-only fallback. Never put secrets in query parameters."""
    try:
        event = append_work(actor, project, task, status, text, next)
        return (
            "WRITE_OK\n"
            f"id={event['id']}\n"
            f"actor={event['actor']}\n"
            f"project={event['project']}\n"
            f"status={event['status']}\n"
            f"created_at={event['created_at']}\n"
            "trust=UNVERIFIED\n"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/gcgw/snapshot")
def gcgw_snapshot_json(after_board: int = 0, after_work: int = 0, project: str | None = None):
    return gcgw_snapshot(after_board, after_work, project)


@app.get("/gcgw/snapshot.txt", response_class=PlainTextResponse)
def gcgw_snapshot_text(project: str | None = None):
    return gcgw_board_text(project=project) + "\n\n" + gcgw_work_text(project=project)


@app.get("/api/tables")
def cafe_tables():
    return {"ok": True, "tables": cafe_list_tables()}


@app.post("/api/tables", status_code=201)
def cafe_table_create(request: CafeTableCreateRequest):
    try:
        table = cafe_create_table(
            title=request.title,
            password=request.password,
            expires_in_hours=request.expires_in_hours,
        )
        return {"ok": True, "table": table}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _cafe_error(exc: Exception) -> HTTPException:
    message = str(exc).strip("'")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=message)
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@app.get("/api/tables/{room_id}")
def cafe_table_info(
    room_id: str,
    x_table_password: str | None = Header(default=None, alias="X-Table-Password"),
):
    try:
        return {"ok": True, "table": cafe_get_table(room_id, x_table_password or "")}
    except (PermissionError, KeyError, ValueError) as exc:
        raise _cafe_error(exc) from exc


@app.get("/api/tables/{room_id}/messages")
def cafe_messages(
    room_id: str,
    after: int = 0,
    x_table_password: str | None = Header(default=None, alias="X-Table-Password"),
):
    try:
        return {
            "ok": True,
            "messages": cafe_list_messages(room_id, x_table_password or "", after),
        }
    except (PermissionError, KeyError, ValueError) as exc:
        raise _cafe_error(exc) from exc


@app.post("/api/tables/{room_id}/messages", status_code=201)
def cafe_message_post(
    room_id: str,
    request: CafeMessageRequest,
    x_table_password: str | None = Header(default=None, alias="X-Table-Password"),
):
    try:
        message = cafe_post_message(
            room_id=room_id,
            password=x_table_password or "",
            display_name=request.display_name,
            actor_type=request.actor_type,
            body=request.body,
        )
        return {"ok": True, "message": message}
    except (PermissionError, KeyError, ValueError) as exc:
        raise _cafe_error(exc) from exc


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
        "external_free_region": public_context(shared_context()),
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
            history=[item.model_dump() for item in request.history],
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


# Static shared surfaces. Keep mounts last so API routes remain authoritative.
app.mount("/board", StaticFiles(directory=BOARD_DIR, html=True), name="shared-board")
app.mount("/cafe", StaticFiles(directory=CAFE_DIR, html=True), name="ai-cafe")
