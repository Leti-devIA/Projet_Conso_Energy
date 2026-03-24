"""
Routes pour permettre à Fabric de récupérer les événements d'outbox en mode pull.

Endpoints:
- GET  /fabric-exports/pending : lit les événements non acquittés
- POST /fabric-exports/ack     : acquitte des event_id et les retire de l'outbox
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fabric-exports", tags=["FabricExports"])
OUTBOX_PATH = Path(__file__).resolve().parents[4] / "exports" / "fabric_outbox.jsonl"


class PendingEventsResponse(BaseModel):
    total_pending: int
    items: List[Dict[str, Any]]


class AckRequest(BaseModel):
    event_ids: List[str] = Field(default_factory=list)


class AckResponse(BaseModel):
    requested: int
    removed: int
    remaining: int


def _line_fallback_event_id(raw_line: str) -> str:
    digest = hashlib.sha256(raw_line.encode("utf-8")).hexdigest()[:24]
    return f"legacy-{digest}"


def _read_outbox() -> List[Dict[str, Any]]:
    if not OUTBOX_PATH.exists():
        return []

    items: List[Dict[str, Any]] = []
    with OUTBOX_PATH.open("r", encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                logger.warning("⚠️ Ligne outbox JSON invalide ignorée")
                continue

            if not isinstance(event, dict):
                continue

            event_id = event.get("event_id")
            if not event_id:
                event_id = _line_fallback_event_id(line)
                event["event_id"] = event_id

            items.append(event)

    return items


def _write_outbox(items: List[Dict[str, Any]]) -> None:
    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX_PATH.open("w", encoding="utf-8") as stream:
        for event in items:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


@router.get(
    "/pending",
    response_model=PendingEventsResponse,
    summary="Lister les événements outbox en attente",
)
async def get_pending_events(
    limit: int = 100,
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> PendingEventsResponse:
    try:
        require_api_key(x_api_key)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if limit <= 0:
        limit = 1
    if limit > 5000:
        limit = 5000

    items = _read_outbox()
    return PendingEventsResponse(total_pending=len(items), items=items[:limit])


@router.post(
    "/ack",
    response_model=AckResponse,
    summary="Acquitter des événements outbox",
)
async def ack_events(
    payload: AckRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> AckResponse:
    try:
        require_api_key(x_api_key)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not payload.event_ids:
        items = _read_outbox()
        return AckResponse(requested=0, removed=0, remaining=len(items))

    wanted = set(payload.event_ids)
    before = _read_outbox()
    after = [event for event in before if event.get("event_id") not in wanted]

    _write_outbox(after)

    return AckResponse(
        requested=len(payload.event_ids),
        removed=len(before) - len(after),
        remaining=len(after),
    )


@router.get(
    "/health",
    summary="Santé du canal d'export Fabric",
)
async def fabric_exports_health() -> Dict[str, Any]:
    items = _read_outbox()
    return {
        "status": "ok",
        "outbox_path": str(OUTBOX_PATH),
        "pending": len(items),
    }
