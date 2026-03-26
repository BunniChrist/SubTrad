from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

try:
    from backend.services.lead_store import LeadStore
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from services.lead_store import LeadStore


router = APIRouter(prefix="/api", tags=["leads"])
lead_store = LeadStore()
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


@router.post("/leads")
def create_lead(request: LeadCreateRequest) -> JSONResponse:
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
