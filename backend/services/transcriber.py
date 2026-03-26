from __future__ import annotations

from pathlib import Path

from openai import OpenAI


def transcribe_audio_with_metadata(
    audio_path: str,
    api_key: str,
) -> dict[str, list[dict[str, float | str]] | str | None]:
    path = Path(audio_path)
    if not path.exists() or path.stat().st_size == 0:
        return {"segments": [], "language": None}

    client = OpenAI(api_key=api_key)
    with path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = getattr(response, "segments", None) or []
    return {
        "segments": [
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text),
            }
            for segment in segments
        ],
        "language": getattr(response, "language", None),
    }


def transcribe_audio(audio_path: str, api_key: str) -> list[dict[str, float | str]]:
    return list(transcribe_audio_with_metadata(audio_path, api_key)["segments"])
