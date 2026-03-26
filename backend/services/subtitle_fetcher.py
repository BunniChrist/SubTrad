from __future__ import annotations

import httpx
from yt_dlp import YoutubeDL


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


def _find_best_track(tracks: list[dict]) -> dict | None:
    """Find the best subtitle track from a list, preferring srv3 > vtt > srt."""
    for fmt in _PREFERRED_FORMATS:
        for track in tracks:
            if track.get("ext") == fmt and track.get("url"):
                return track
    return None


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


def fetch_existing_subtitles(
    url: str,
    proxy: str = "",
    cookie_file: str | None = None,
) -> list[dict[str, str]] | None:
    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
    }
    if proxy:
        options["proxy"] = proxy
    if cookie_file:
        options["cookiefile"] = cookie_file

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    subtitle_groups = [
        info.get("subtitles") or {},
        info.get("automatic_captions") or {},
    ]

    client_kwargs = {"timeout": 15}
    if proxy:
        client_kwargs["proxy"] = proxy

    for group in subtitle_groups:
        for tracks in group.values():
            track = _find_best_track(tracks)
            if not track:
                continue
            try:
                resp = httpx.get(track["url"], **client_kwargs)
                if resp.status_code == 200 and resp.text.strip():
                    segments = _parse_track_content(resp.text, track["ext"])
                    if segments:
                        return segments
            except Exception:
                continue

    return None
