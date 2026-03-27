from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from yt_dlp import YoutubeDL

try:
    from backend.services.warp_rotator import is_youtube_block, rotate_warp_ip
except ModuleNotFoundError:  # pragma: no cover
    from services.warp_rotator import is_youtube_block, rotate_warp_ip


# Formats in priority order: srv3 (XML, best parsed), vtt, srt
_PREFERRED_FORMATS = ("srv3", "vtt", "srt")


def parse_srt(srt_content: str) -> list[dict[str, str]]:
    if not srt_content.strip():
        return []

    entries: list[dict[str, str]] = []
    for block in srt_content.strip().split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        timing = lines[1].split(" --> ")
        if len(timing) != 2:
            continue

        entries.append(
            {
                "start": timing[0],
                "end": timing[1],
                "text": " ".join(lines[2:]),
            }
        )

    return entries


def _parse_vtt(vtt_content: str) -> list[dict[str, str]]:
    """Minimal WebVTT parser."""
    if not vtt_content.strip():
        return []

    entries: list[dict[str, str]] = []
    blocks = vtt_content.strip().split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if " --> " in line:
                timing = line.split(" --> ")
                if len(timing) == 2:
                    start = timing[0].split()[-1]
                    end = timing[1].split()[0]
                    text = " ".join(lines[i + 1:])
                    if text:
                        entries.append({"start": start, "end": end, "text": text})
                break

    return entries


def _parse_track_content(content: str, ext: str) -> list[dict[str, str]]:
    """Parse subtitle content based on format."""
    if ext == "srv3":
        try:
            from backend.services.youtube_api import parse_timedtext_xml
        except ModuleNotFoundError:  # pragma: no cover
            from services.youtube_api import parse_timedtext_xml
        return parse_timedtext_xml(content)
    elif ext == "vtt":
        return _parse_vtt(content)
    else:
        return parse_srt(content)


def get_settings():
    try:
        from backend.config import get_settings as _get_settings
    except ModuleNotFoundError:  # pragma: no cover
        from config import get_settings as _get_settings
    return _get_settings()


def fetch_existing_subtitles(
    url: str,
    proxy: str = "",
    cookie_file: str | None = None,
) -> list[dict[str, str]] | None:
    temp_dir = tempfile.mkdtemp(prefix="subtrad_")
    download_failed = False
    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "srv3",
        "subtitleslangs": ["all"],
        "outtmpl": str(Path(temp_dir) / "%(id)s"),
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
        "extractor_args": {"youtube": {"player_client": ["web", "default"]}},
    }
    if proxy:
        options["proxy"] = proxy
    if cookie_file:
        options["cookiefile"] = cookie_file

    def _download_with_ytdlp() -> None:
        with YoutubeDL(options) as ydl:
            ydl.download([url])

    try:
        _download_with_ytdlp()
    except Exception as exc:
        download_failed = True
        if is_youtube_block(exc):
            rotation_url = get_settings().warp_rotation_url
            if rotation_url and rotate_warp_ip(rotation_url):
                try:
                    _download_with_ytdlp()
                    download_failed = False
                except Exception:
                    download_failed = True
    try:
        for ext in _PREFERRED_FORMATS:
            for subtitle_file in sorted(Path(temp_dir).glob(f"*.{ext}")):
                content = subtitle_file.read_text(encoding="utf-8")
                segments = _parse_track_content(content, ext)
                if segments:
                    return segments
        if download_failed:
            return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return None
