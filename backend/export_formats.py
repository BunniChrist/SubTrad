from __future__ import annotations


def _as_seconds(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _format_vtt_timestamp(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{milliseconds:03}"


def _format_md_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def _clean_text(segment: dict[str, object]) -> str:
    return str(segment.get("text", "")).strip()


def to_vtt(segments: list[dict[str, object]]) -> str:
    if not segments:
        return "WEBVTT\n"

    lines = ["WEBVTT", ""]
    for segment in segments:
        text = _clean_text(segment)
        if not text:
            continue
        lines.append(
            f"{_format_vtt_timestamp(_as_seconds(segment.get('start', 0.0)))} --> "
            f"{_format_vtt_timestamp(_as_seconds(segment.get('end', 0.0)))}"
        )
        lines.append(text)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_txt(segments: list[dict[str, object]]) -> str:
    return "\n".join(
        text for text in (_clean_text(segment) for segment in segments) if text
    )


def to_md(segments: list[dict[str, object]], metadata: dict[str, object]) -> str:
    header_lines = ["---"]
    for key, value in metadata.items():
        header_lines.append(f"{key}: {value}")
    header_lines.append("---")

    if not segments:
        return "\n".join(header_lines) + "\n"

    body_lines: list[str] = []
    last_marker_bucket = -1
    for segment in segments:
        text = _clean_text(segment)
        if not text:
            continue
        start_seconds = _as_seconds(segment.get("start", 0.0))
        marker_bucket = int(start_seconds // 30)
        marker = _format_md_timestamp(marker_bucket * 30)
        if marker_bucket != last_marker_bucket:
            body_lines.append(f"[{marker}] {text}")
            last_marker_bucket = marker_bucket
        else:
            body_lines.append(text)

    return "\n".join(header_lines) + "\n\n" + "\n\n".join(body_lines)
