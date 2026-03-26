from __future__ import annotations

from pathlib import Path

from openai import OpenAI


def transcribe_audio(audio_path: str, api_key: str) -> list[dict[str, float | str]]:
    path = Path(audio_path)
    if not path.exists() or path.stat().st_size == 0:
        return []

    client = OpenAI(api_key=api_key)
    with path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = getattr(response, "segments", None) or []
    return [
        {
            "start": float(segment.start),
            "end": float(segment.end),
            "text": str(segment.text),
        }
        for segment in segments
    ]
