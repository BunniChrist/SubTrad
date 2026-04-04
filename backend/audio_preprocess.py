from __future__ import annotations

import subprocess
from pathlib import Path


def build_preprocessed_audio_path(source: Path) -> Path:
    return source.with_suffix(".preprocessed.wav")


def preprocess_audio(audio_path: str) -> str:
    source = Path(audio_path)
    output = build_preprocessed_audio_path(source)

    if output.exists() and output.stat().st_size > 0:
        return str(output)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-af",
            (
                "loudnorm,"
                "silenceremove="
                "start_periods=1:start_silence=0.3:start_threshold=-35dB:"
                "stop_periods=1:stop_silence=0.5:stop_threshold=-35dB"
            ),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return str(output)
