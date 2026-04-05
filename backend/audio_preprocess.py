from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def build_preprocessed_audio_path(source: Path) -> Path:
    return source.with_suffix(".preprocessed.wav")


def cleanup_preprocessed(path: str | Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        return


def preprocess_audio(audio_path: str) -> str:
    source = Path(audio_path)
    output = build_preprocessed_audio_path(source)

    if output.exists() and output.stat().st_size > 0:
        return str(output)

    fd, temp_name = tempfile.mkstemp(
        prefix=f"{output.stem}.",
        suffix=".tmp.wav",
        dir=output.parent,
    )
    os.close(fd)
    temp_output = Path(temp_name)

    try:
        try:
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
                    str(temp_output),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip()
            raise ValueError(f"Audio preprocessing failed: {stderr}") from exc

        if output.exists() and output.stat().st_size > 0:
            return str(output)

        os.replace(temp_output, output)
        return str(output)
    finally:
        cleanup_preprocessed(temp_output)
