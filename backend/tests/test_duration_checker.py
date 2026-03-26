from backend.services.duration_checker import DurationResult, check_duration


def test_check_duration_allows_videos_below_limit() -> None:
    assert check_duration(600) == DurationResult(
        allowed=True,
        duration_seconds=600,
        redirect=None,
    )


def test_check_duration_allows_videos_at_limit() -> None:
    assert check_duration(720) == DurationResult(
        allowed=True,
        duration_seconds=720,
        redirect=None,
    )


def test_check_duration_rejects_videos_over_limit() -> None:
    assert check_duration(721) == DurationResult(
        allowed=False,
        duration_seconds=721,
        redirect="premium",
    )
