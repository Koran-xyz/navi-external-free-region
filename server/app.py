"""HTTP gateway for browser chat -> Notion append-only writer."""
from __future__ import annotations

import hmac
import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.notion_writer import NotionWriterError, append_record

app = FastAPI(title="Navi External Free Region Gateway", version="0.1.0")

allowed_origin = os.getenv("ALLOWED_ORIGIN", "").strip()
if allowed_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin],
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Authorization", "Content-Type"],
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


def _authorize(authorization: str | None) -> None:
    expected = os.getenv("GATEWAY_WRITE_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="gateway key is not configured")

    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/notion/log")
def create_log(record: WorkRecord, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return append_record(record.model_dump())
    except NotionWriterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
