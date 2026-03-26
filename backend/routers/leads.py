from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

try:
    from backend.services.lead_store import LeadStore
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from services.lead_store import LeadStore


router = APIRouter(prefix="/api", tags=["leads"])
lead_store = LeadStore()
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Simple in-memory rate limiter: max 5 POST /leads per IP per 60 seconds
_rate_limit_window = 60
_rate_limit_max = 5
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


class LeadCreateRequest(BaseModel):
    email: str
    type: Literal["premium", "suggestion"]
    message: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email address")
        return normalized


def _is_rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    timestamps = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < _rate_limit_window]
    if len(_rate_limit_store[client_ip]) >= _rate_limit_max:
        return True
    _rate_limit_store[client_ip].append(now)
    return False


@router.post("/leads")
def create_lead(request: LeadCreateRequest, raw_request: Request) -> JSONResponse:
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if _is_rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests, please try again later"},
        )
    if lead_store.lead_exists(request.email, request.type):
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_registered",
                "total_signups": lead_store.get_lead_count(request.type),
            },
        )

    lead_id = lead_store.save_lead(request.email, request.type, request.message)
    return JSONResponse(
        status_code=201,
        content={
            "status": "ok",
            "lead_id": lead_id,
            "total_signups": lead_store.get_lead_count(request.type),
        },
    )


@router.get("/leads/count")
def get_lead_count(
    type: Literal["premium", "suggestion"] = Query(...),
) -> dict[str, int | str]:
    return {"type": type, "count": lead_store.get_lead_count(type)}
