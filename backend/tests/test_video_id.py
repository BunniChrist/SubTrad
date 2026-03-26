import pytest

from backend.services.video_id import extract_video_id


@pytest.mark.parametrize(
    ("url", "platform", "expected_video_id"),
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "youtube",
            "dQw4w9WgXcQ",
        ),
        ("https://youtu.be/dQw4w9WgXcQ?t=43", "youtube", "dQw4w9WgXcQ"),
        (
            "https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share",
            "youtube",
            "dQw4w9WgXcQ",
        ),
        (
            "https://www.tiktok.com/@user/video/7123456789?lang=en",
            "tiktok",
            "7123456789",
        ),
        (
            "https://www.instagram.com/reel/CxYz123Ab/?utm_source=ig_web_copy_link",
            "instagram",
            "CxYz123Ab",
        ),
    ],
)
def test_extract_video_id_returns_expected_identifier(
    url: str, platform: str, expected_video_id: str
) -> None:
    assert extract_video_id(url, platform) == expected_video_id


def test_extract_video_id_rejects_unsupported_platform() -> None:
    with pytest.raises(ValueError):
        extract_video_id("https://example.com/video/123", "example")
