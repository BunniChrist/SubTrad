import re


PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "youtube": (
        re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:[&?].*)?$"),
        re.compile(r"^https?://youtu\.be/[\w-]+(?:[?].*)?$"),
        re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/[\w-]+(?:[?].*)?$"),
    ),
    "tiktok": (
        re.compile(r"^https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+(?:[?].*)?$"),
        re.compile(r"^https?://vm\.tiktok\.com/[\w-]+/?(?:[?].*)?$"),
    ),
    "instagram": (
        re.compile(r"^https?://(?:www\.)?instagram\.com/reel/[\w-]+/?(?:[?].*)?$"),
        re.compile(r"^https?://(?:www\.)?instagram\.com/p/[\w-]+/?(?:[?].*)?$"),
    ),
}


def detect_platform(url: str) -> str | None:
    if not url:
        return None

    normalized_url = url.strip()
    for platform, patterns in PATTERNS.items():
        if any(pattern.match(normalized_url) for pattern in patterns):
            return platform
    return None


def validate_url(url: str) -> bool:
    return detect_platform(url) is not None
