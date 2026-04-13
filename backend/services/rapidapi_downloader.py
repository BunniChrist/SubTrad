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
        (settings.rapidapi_host_3 or "").strip(),
    ]
    hosts = [host for host in hosts if host]

    if not rapidapi_key or not hosts:
        raise RuntimeError("RapidAPI fallback is not configured")

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

    if host == "youtube-mp3-audio-video-downloader.p.rapidapi.com":
        # Provider endpoint appears unstable; keep a small probe set.
        return [
            ("/v1/video/details", {"videoId": video_id}),
            ("/v2/video/details", {"videoId": video_id}),
            ("/details", {"videoId": video_id}),
        ]

    if host == "youtube-video-fast-downloader-24-7.p.rapidapi.com":
        return [
            (f"/get_available_quality/{video_id}", None),
        ]

    # Generic fallback for future host substitutions.
    return [
        ("/v2/video/details", {"videoId": video_id}),
        ("/v2/video/details", {"url": source_url}),
    ]


def _find_download_url(payload: object) -> str | None:
    if isinstance(payload, str):
        if payload.startswith("http"):
            return payload
        return None

    if isinstance(payload, list):
        for item in payload:
            found = _find_download_url(item)
            if found:
                return found
        return None

    if not isinstance(payload, dict):
        return None

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

    for key in preferred_keys:
        if key in payload:
            found = _find_download_url(payload[key])
            if found and _looks_like_media_url(found):
                return found

    for value in payload.values():
        found = _find_download_url(value)
        if found and _looks_like_media_url(found):
            return found

    for value in payload.values():
        found = _find_download_url(value)
        if found:
            return found

    return None


def _looks_like_media_url(value: str) -> bool:
    lowered = value.lower()
    if any(ext in lowered for ext in AUDIO_EXTENSIONS):
        return True
    return "audio" in lowered or "download" in lowered


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
