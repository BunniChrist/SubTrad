from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, content: dict[str, object]) -> None:
        super().__init__(status_code=status_code, detail=content)
