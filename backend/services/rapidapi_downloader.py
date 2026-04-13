from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import requests

try:
    from backend.services.video_id import extract_video_id
except ModuleNotFoundError:  # pragma: no cover
    from services.video_id import extract_video_id


logger = logging.getLogger(__name__)
TEMP_AUDIO_DIR = Path("/tmp/subtrad")
AUDIO_EXTENSIONS = (".m4a", ".mp3", ".webm", ".aac", ".ogg", ".wav", ".mp4")


def get_settings():
    try:
        from backend.config import get_settings as _get_settings
    except ModuleNotFoundError:  # pragma: no cover
        from config import get_settings as _get_settings
    return _get_settings()


def extract_audio_via_rapidapi(url: str, timeout: float = 25.0) -> str:
    settings = get_settings()
    rapidapi_key = (settings.rapidapi_key or "").strip()
    hosts = [
        (settings.rapidapi_host_1 or "").strip(),
        (settings.rapidapi_host_2 or "").strip(),
    ]
    hosts = [host for host in hosts if host]

    if not rapidapi_key or not hosts:
        raise RuntimeError("RapidAPI audio extraction is not configured")

    video_id = extract_video_id(url, "youtube")
    failures: list[str] = []

    for host in hosts:
        try:
            download_url = _resolve_download_url(
                host=host,
                rapidapi_key=rapidapi_key,
                source_url=url,
                video_id=video_id,
                timeout=timeout,
            )
            if not download_url:
                raise RuntimeError("empty download URL")
            return _download_media_file(download_url, timeout=timeout)
        except Exception as exc:
            failures.append(f"{host}: {exc}")
            logger.warning("RapidAPI fallback failed for host %s: %s", host, exc)

    raise RuntimeError(
        "All RapidAPI download hosts failed: " + " | ".join(failures)
    )


def _resolve_download_url(
    *,
    host: str,
    rapidapi_key: str,
    source_url: str,
    video_id: str,
    timeout: float,
) -> str:
    request_candidates = _request_candidates(host, source_url=source_url, video_id=video_id)
    for path, params in request_candidates:
        response = _rapidapi_get(
            host=host,
            rapidapi_key=rapidapi_key,
            path=path,
            params=params,
            timeout=timeout,
        )
        payload = response.json()
        download_url = _find_download_url(payload)
        if download_url:
            return download_url
    raise RuntimeError("no downloadable media URL in API response")


def _rapidapi_get(
    *,
    host: str,
    rapidapi_key: str,
    path: str,
    params: dict[str, str] | None,
    timeout: float,
):
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": host,
    }
    response = requests.get(
        f"https://{host}{path}",
        headers=headers,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _request_candidates(host: str, *, source_url: str, video_id: str) -> list[tuple[str, dict[str, str] | None]]:
    # Endpoint structures validated against live host responses.
    if host == "youtube-media-downloader.p.rapidapi.com":
        return [
            ("/v2/video/details", {"videoId": video_id}),
        ]

    if host == "youtube-search-and-download.p.rapidapi.com":
        return [
            ("/video/download", {"id": video_id}),
            ("/video", {"id": video_id}),
        ]

    # Generic fallback for future host substitutions within the two-provider setup.
    return [
        ("/v2/video/details", {"videoId": video_id}),
        ("/video/download", {"id": video_id}),
    ]


def _find_download_url(payload: object) -> str | None:
    best_score = -1
    best_url: str | None = None
    for url, score in _iter_scored_urls(payload):
        if score > best_score:
            best_score = score
            best_url = url
    return best_url


def _iter_scored_urls(payload: object):
    if isinstance(payload, str):
        if payload.startswith("http"):
            score = _score_media_url(payload, context_key=None)
            if score > 0:
                yield payload, score
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _iter_scored_urls(item)
        return

    if not isinstance(payload, dict):
        return

    mime_value = str(payload.get("mimeType") or payload.get("mime") or "").lower()
    context_bonus = 0
    if "audio" in mime_value:
        context_bonus += 60
    elif "video" in mime_value:
        context_bonus += 45

    preferred_keys = (
        "downloadUrl",
        "download_url",
        "audioUrl",
        "audio_url",
        "audio",
        "url",
        "link",
        "src",
    )
    seen_values: set[int] = set()

    for key in preferred_keys:
        if key not in payload:
            continue
        value = payload[key]
        seen_values.add(id(value))
        if isinstance(value, str):
            score = _score_media_url(value, context_key=key) + context_bonus
            if score > 0:
                yield value, score
        else:
            yield from _iter_scored_urls(value)

    for key, value in payload.items():
        if id(value) in seen_values:
            continue
        if isinstance(value, str):
            score = _score_media_url(value, context_key=key) + context_bonus
            if score > 0:
                yield value, score
        else:
            yield from _iter_scored_urls(value)


def _looks_like_media_url(value: str) -> bool:
    return _score_media_url(value, context_key=None) > 0


def _score_media_url(value: str, *, context_key: str | None) -> int:
    lowered = value.lower()
    if not lowered.startswith("http"):
        return 0

    if any(marker in lowered for marker in ("ytimg.com", "ggpht.com", "i.ytimg.com")):
        return 0
    if any(marker in lowered for marker in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return 0

    score = 1

    if "googlevideo.com/videoplayback" in lowered:
        score += 35
    if "manifest.googlevideo.com" in lowered:
        score += 5
    if any(ext in lowered for ext in AUDIO_EXTENSIONS):
        score += 30
    if "mime=audio" in lowered or "audio/" in lowered:
        score += 30
    if "mime=video" in lowered or "video/" in lowered:
        score += 20
    if "download" in lowered:
        score += 15
    if "m3u8" in lowered:
        score -= 10

    if context_key:
        lowered_key = context_key.lower()
        if "audio" in lowered_key:
            score += 20
        elif "video" in lowered_key:
            score += 10
        elif "download" in lowered_key:
            score += 10
        elif lowered_key in {"thumbnail", "avatar", "image", "poster"}:
            score -= 30

    return max(score, 0)


def _download_media_file(download_url: str, timeout: float) -> str:
    response = requests.get(
        download_url,
        timeout=timeout,
        stream=True,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Referer": "https://www.youtube.com/",
        },
    )
    response.raise_for_status()

    content_type = ""
    if hasattr(response, "headers") and isinstance(response.headers, dict):
        content_type = response.headers.get("Content-Type", "")

    file_suffix = _guess_suffix(download_url, content_type)
    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(prefix="rapidapi_", suffix=file_suffix, dir=str(TEMP_AUDIO_DIR))
    total_bytes = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                handle.write(chunk)
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise

    if total_bytes == 0:
        Path(temp_path).unlink(missing_ok=True)
        raise RuntimeError("RapidAPI returned an empty media payload")

    return temp_path


def _guess_suffix(download_url: str, content_type: str) -> str:
    lowered_url = download_url.lower()
    for extension in AUDIO_EXTENSIONS:
        if extension in lowered_url:
            return extension

    lowered_content_type = (content_type or "").lower()
    if "mpeg" in lowered_content_type:
        return ".mp3"
    if "mp4" in lowered_content_type:
        return ".m4a"
    if "webm" in lowered_content_type:
        return ".webm"
    if "ogg" in lowered_content_type:
        return ".ogg"

    return ".m4a"
