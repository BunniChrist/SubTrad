from dataclasses import dataclass


@dataclass(frozen=True)
class DurationResult:
    allowed: bool
    duration_seconds: int
    redirect: str | None


def check_duration(duration_seconds: int) -> DurationResult:
    if duration_seconds <= 720:
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
