import pytest

from backend.services.url_validator import detect_platform, validate_url


@pytest.mark.parametrize(
    ("url", "expected_platform"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "youtube"),
        ("https://www.tiktok.com/@user/video/7123456789", "tiktok"),
        ("https://vm.tiktok.com/ZM1234567/", "tiktok"),
        ("https://www.instagram.com/reel/CxYz123Ab/", "instagram"),
        ("https://www.instagram.com/p/CxYz123Ab/", "instagram"),
    ],
)
def test_validate_url_accepts_supported_platform_formats(
    url: str, expected_platform: str
) -> None:
    assert validate_url(url) is True
    assert detect_platform(url) == expected_platform


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        "https://example.com/video/123",
        "https://www.youtube.com/",
        "https://www.instagram.com/stories/user/123",
    ],
)
def test_validate_url_rejects_invalid_or_unsupported_urls(url: str) -> None:
    assert validate_url(url) is False
    assert detect_platform(url) is None
