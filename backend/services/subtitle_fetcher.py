from __future__ import annotations

from yt_dlp import YoutubeDL


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


def fetch_existing_subtitles(url: str) -> list[dict[str, str]] | None:
    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    subtitle_groups = [
        info.get("subtitles") or {},
        info.get("automatic_captions") or {},
    ]

    for group in subtitle_groups:
        for tracks in group.values():
            for track in tracks:
                if track.get("ext") != "srt":
                    continue
                subtitle_url = track.get("url")
                if subtitle_url:
                    return [{"start": "00:00:00,000", "end": "00:00:00,000", "text": subtitle_url}]

    return None
