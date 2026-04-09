from dataclasses import dataclass

try:
    from backend.config import get_settings
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from config import get_settings


@dataclass(frozen=True)
class DurationResult:
    allowed: bool
    duration_seconds: int
    redirect: str | None


def check_duration(duration_seconds: int) -> DurationResult:
    if duration_seconds <= get_settings().max_duration_seconds:
        return DurationResult(
            allowed=True,
            duration_seconds=duration_seconds,
            redirect=None,
        )

    return DurationResult(
        allowed=False,
        duration_seconds=duration_seconds,
        redirect="premium",
    )
