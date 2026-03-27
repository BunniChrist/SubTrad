"""YouTube Data API v3 service for video info and caption retrieval."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
try:
    from youtube_transcript_api._errors import RequestBlocked
except ImportError:  # pragma: no cover
    RequestBlocked = Exception

try:
    from backend.services.subtitle_fetcher import fetch_existing_subtitles
except ModuleNotFoundError:  # pragma: no cover
    from services.subtitle_fetcher import fetch_existing_subtitles
try:
    from backend.services.warp_rotator import is_youtube_block, rotate_warp_ip
except ModuleNotFoundError:  # pragma: no cover
    from services.warp_rotator import is_youtube_block, rotate_warp_ip


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
TIMEDTEXT_BASE = "https://www.youtube.com/api/timedtext"
DEFAULT_TRANSCRIPT_LANGS = ["en", "fr", "es", "ja", "de", "pt", "it", "ar", "zh", "ko", "ru"]
logger = logging.getLogger(__name__)


def get_settings():
    try:
        from backend.config import get_settings as _get_settings
    except ModuleNotFoundError:  # pragma: no cover
        from config import get_settings as _get_settings
    return _get_settings()


def parse_iso8601_duration(duration: str) -> int:
    """Parse ISO 8601 duration (e.g. PT1H2M30S) into total seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def parse_timedtext_xml(xml_content: str) -> list[dict[str, str]]:
    """Parse YouTube timedtext XML into subtitle segments."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    segments = []
    for text_elem in root.findall(".//text"):
        start = float(text_elem.get("start", "0"))
        dur = float(text_elem.get("dur", "0"))
        content = text_elem.text or ""
        if not content.strip():
            continue
        segments.append({
            "start": f"{start:.3f}",
            "end": f"{start + dur:.3f}",
            "text": content,
        })

    if segments:
        return segments

    for paragraph_elem in root.findall(".//p"):
        start_ms = float(paragraph_elem.get("t", "0"))
        dur_ms = float(paragraph_elem.get("d", "0"))
        content = "".join(paragraph_elem.itertext())
        if not content.strip():
            continue

        start = start_ms / 1000
        dur = dur_ms / 1000
        segments.append({
            "start": f"{start:.3f}",
            "end": f"{start + dur:.3f}",
            "text": content,
        })

    return segments


def get_video_info(video_id: str, api_key: str) -> dict | None:
    """Get video duration and metadata via YouTube Data API v3.

    Returns dict with duration_seconds and title, or None if video not found.
    Raises RuntimeError on API errors.
    """
    url = f"{YOUTUBE_API_BASE}/videos"
    params = {
        "part": "contentDetails,snippet",
        "id": video_id,
        "key": api_key,
    }
    response = httpx.get(url, params=params, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(
            f"YouTube API error {response.status_code}: {response.text}"
        )

    data = response.json()
    items = data.get("items", [])
    if not items:
        return None

    item = items[0]
    duration_str = item["contentDetails"]["duration"]
    title = item["snippet"].get("title", "")
    default_audio_language = (
        item["snippet"].get("defaultAudioLanguage")
        or item["snippet"].get("defaultLanguage")
    )

    return {
        "duration_seconds": parse_iso8601_duration(duration_str),
        "title": title,
        "default_audio_language": default_audio_language,
    }


def fetch_captions(
    video_id: str,
    target_lang: str,
    api_key: str,
    proxy: str = "",
    cookie_file: str | None = None,
) -> list[dict[str, str]] | None:
    subtitles, _source = fetch_captions_with_source(
        video_id,
        target_lang,
        api_key,
        proxy=proxy,
        cookie_file=cookie_file,
    )
    return subtitles


def fetch_captions_with_source(
    video_id: str,
    target_lang: str,
    api_key: str,
    proxy: str = "",
    cookie_file: str | None = None,
) -> tuple[list[dict[str, str]] | list[dict[str, float | str]] | None, str | None]:
    """Fetch captions for a YouTube video.

    0. Tries youtube-transcript-api fast path
    1. Lists available caption tracks via API v3
    2. Tries to download via public timedtext endpoint
    3. Falls back to yt-dlp if timedtext fails

    Returns subtitle segments with a source identifier, or (None, None).
    """
    segments = fetch_captions_via_transcript_lib(
        video_id,
        preferred_langs=_build_transcript_language_candidates(target_lang),
    )
    if segments:
        return segments, "youtube_transcript_api"

    # Step 1: List available caption tracks
    url = f"{YOUTUBE_API_BASE}/captions"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "key": api_key,
    }
    response = httpx.get(url, params=params, timeout=10)

    if response.status_code != 200:
        return None, None

    data = response.json()
    tracks = data.get("items", [])
    if not tracks:
        for language in _build_asr_language_candidates(video_id, target_lang, api_key):
            segments = _fetch_timedtext_segments(video_id, language, asr=True, proxy=proxy)
            if segments:
                return segments, "existing_captions"
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        return fetch_existing_subtitles(
            youtube_url,
            proxy=proxy,
            cookie_file=cookie_file,
        ), "existing_captions"

    # Step 2: Pick the best track (prefer source language, avoid target_lang)
    # Fetching subtitles already in the target language would cause the
    # translator to detect same-language and skip translation entirely.
    languages = [t["snippet"]["language"] for t in tracks]
    source_languages = [lang for lang in languages if lang != target_lang]
    chosen_lang = source_languages[0] if source_languages else languages[0]

    # Step 3: Try timedtext endpoint
    segments = _fetch_timedtext_segments(video_id, chosen_lang, proxy=proxy)
    if segments:
        return segments, "existing_captions"

    segments = _fetch_timedtext_segments(video_id, chosen_lang, asr=True, proxy=proxy)
    if segments:
        return segments, "existing_captions"

    # Step 4: Fall back to yt-dlp
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    return fetch_existing_subtitles(
        youtube_url,
        proxy=proxy,
        cookie_file=cookie_file,
    ), "existing_captions"


def fetch_captions_via_transcript_lib(
    video_id: str,
    preferred_langs: list[str] | None = None,
) -> list[dict[str, float | str]] | None:
    """Fast path: fetch captions via youtube-transcript-api."""
    languages = preferred_langs or list(DEFAULT_TRANSCRIPT_LANGS)
    transcript_api = YouTubeTranscriptApi()

    try:
        transcript = transcript_api.fetch(video_id, languages=languages)
    except Exception as exc:
        if isinstance(exc, RequestBlocked) or is_youtube_block(exc):
            rotation_url = get_settings().warp_rotation_url
            if rotation_url and rotate_warp_ip(rotation_url):
                try:
                    transcript = transcript_api.fetch(video_id, languages=languages)
                except Exception as retry_exc:
                    logger.warning(
                        "youtube-transcript-api retry failed for %s: %s",
                        video_id,
                        retry_exc,
                    )
                    return None
            else:
                logger.warning("youtube-transcript-api failed for %s: %s", video_id, exc)
                return None
        else:
            logger.warning("youtube-transcript-api failed for %s: %s", video_id, exc)
            return None

    segments = [
        {
            "text": snippet.text,
            "start": float(snippet.start),
            "duration": float(snippet.duration),
        }
        for snippet in transcript.snippets
        if snippet.text.strip()
    ]
    return segments or None


def _build_transcript_language_candidates(target_lang: str) -> list[str]:
    candidates: list[str] = []

    # Prefer source languages first (any language OTHER than target).
    # The target language is appended last so we only use it as a
    # last resort — fetching subtitles already in the target language
    # causes the translator to skip translation entirely.
    for language in DEFAULT_TRANSCRIPT_LANGS:
        normalized = _normalize_language(language)
        if normalized and normalized != _normalize_language(target_lang) and normalized not in candidates:
            candidates.append(normalized)

    # Append target_lang last as ultimate fallback
    normalized_target = _normalize_language(target_lang)
    if normalized_target and normalized_target not in candidates:
        candidates.append(normalized_target)

    return candidates


def _normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    return language.split("-")[0].strip().lower() or None


def _build_asr_language_candidates(
    video_id: str,
    target_lang: str,
    api_key: str,
) -> list[str]:
    candidates: list[str] = []

    try:
        info = get_video_info(video_id, api_key)
    except RuntimeError:
        info = None

    for language in (
        _normalize_language((info or {}).get("default_audio_language")),
        "en",
        _normalize_language(target_lang),
    ):
        if language and language not in candidates:
            candidates.append(language)

    return candidates


def _fetch_timedtext_segments(
    video_id: str,
    language: str,
    *,
    asr: bool = False,
    proxy: str = "",
) -> list[dict[str, str]]:
    timedtext_params = {"v": video_id, "lang": language, "fmt": "srv3"}
    if asr:
        timedtext_params["kind"] = "asr"

    client_kwargs = {"params": timedtext_params, "timeout": 10}
    if proxy:
        client_kwargs["proxy"] = proxy

    tt_response = httpx.get(TIMEDTEXT_BASE, **client_kwargs)
    if tt_response.status_code != 200 or not tt_response.text.strip():
        return []

    return parse_timedtext_xml(tt_response.text)
