from __future__ import annotations

from pathlib import Path


def build_preprocessed_audio_path(source: Path) -> Path:
    return source.with_suffix(".preprocessed.wav")
