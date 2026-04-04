from __future__ import annotations

import re

TERMINAL_PUNCTUATION = (".", "!", "?", "...")
NOISE_TAG_RE = re.compile(r"^\[(music|applause|laughter|noise)\]$", re.IGNORECASE)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _is_meaningless_short_segment(text: str) -> bool:
    compact = re.sub(r"[^a-z]", "", text.lower())
    return len(compact) <= 2


def cleanup_transcript(
    segments: list[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    cleaned: list[dict[str, float | str]] = []

    for segment in segments:
        text = _normalized_text(segment.get("text", ""))
        if not text:
            continue
        if NOISE_TAG_RE.match(text):
            continue
        if _is_meaningless_short_segment(text):
            continue

        normalized = {
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "text": text,
        }

        if cleaned and cleaned[-1]["text"] == normalized["text"]:
            continue

        if cleaned and not str(cleaned[-1]["text"]).endswith(TERMINAL_PUNCTUATION):
            cleaned[-1] = {
                "start": cleaned[-1]["start"],
                "end": normalized["end"],
                "text": f"{cleaned[-1]['text']} {normalized['text']}",
            }
            continue

        cleaned.append(normalized)

    return cleaned
