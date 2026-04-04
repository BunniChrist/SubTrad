from __future__ import annotations

import time
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ModuleNotFoundError:  # pragma: no cover - dependency may be absent in test env
    WhisperModel = None  # type: ignore[assignment]

try:
    from backend.audio_preprocess import preprocess_audio
    from backend.config import get_settings
    from backend.transcript_cleanup import cleanup_transcript
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from audio_preprocess import preprocess_audio
    from config import get_settings
    from transcript_cleanup import cleanup_transcript


WHISPER_SUPPORTED = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}

_model = None


def _validate_audio_file(path: Path) -> None:
    if not path.exists():
        return
    if path.suffix.lower() not in WHISPER_SUPPORTED:
        raise ValueError(f"Unsupported audio format: {path.suffix}")
    size = path.stat().st_size
    if size == 0:
        return
    if size < 1000:
        raise ValueError(f"Audio file too small ({size} bytes), likely corrupt")


def _get_model():
    global _model
    if _model is None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed")
        _model = WhisperModel(
            get_settings().whisper_model,
            device="cpu",
            compute_type="int8",
        )
    return _model


def transcribe_audio_with_metadata(
    audio_path: str,
    source_lang: str | None = None,
) -> dict[str, list[dict[str, float | str]] | str | None]:
    path = Path(audio_path)
    if not path.exists() or path.stat().st_size == 0:
        return {"segments": [], "language": None}
    _validate_audio_file(path)
    preprocess_started_at = time.perf_counter()
    prepared_audio_path = preprocess_audio(str(path))
    preprocess_elapsed = time.perf_counter() - preprocess_started_at
    model = _get_model()

    try:
        transcription_started_at = time.perf_counter()
        if source_lang:
            segments, info = model.transcribe(
                prepared_audio_path,
                word_timestamps=False,
                vad_filter=True,
                language=source_lang,
            )
        else:
            _, detected_info = model.transcribe(
                prepared_audio_path,
                word_timestamps=False,
                vad_filter=True,
                clip_timestamps="0,30",
            )
            detected_language = getattr(detected_info, "language", None)
            segments, info = model.transcribe(
                prepared_audio_path,
                word_timestamps=False,
                vad_filter=True,
                language=detected_language,
            )
        transcription_elapsed = time.perf_counter() - transcription_started_at
    except Exception as exc:
        raise ValueError(f"Invalid audio file: {path.name}") from exc

    cleaned_segments = cleanup_transcript(
        [
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text),
            }
            for segment in segments
        ]
    )

    return {
        "segments": cleaned_segments,
        "language": getattr(info, "language", None),
        "timings": {
            "preprocess_seconds": round(preprocess_elapsed, 3),
            "transcription_seconds": round(transcription_elapsed, 3),
        },
    }


def transcribe_audio(audio_path: str) -> list[dict[str, float | str]]:
    return list(transcribe_audio_with_metadata(audio_path)["segments"])
