import subprocess
from pathlib import Path

from backend.audio_preprocess import build_preprocessed_audio_path, preprocess_audio


def test_build_preprocessed_audio_path_uses_stable_cache_name(tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")

    path = build_preprocessed_audio_path(source)

    assert path == tmp_path / "clip.preprocessed.wav"


def test_preprocess_audio_runs_ffmpeg_with_expected_filters(monkeypatch, tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")
    commands: list[list[str]] = []

    def fake_run(command: list[str], check: bool, capture_output: bool) -> None:
        assert check is True
        assert capture_output is True
        commands.append(command)
        Path(command[-1]).write_bytes(b"processed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = preprocess_audio(str(source))

    assert result == str(tmp_path / "clip.preprocessed.wav")
    assert commands == [[
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        "loudnorm,silenceremove=start_periods=1:start_silence=0.3:start_threshold=-35dB:stop_periods=1:stop_silence=0.5:stop_threshold=-35dB",
        str(tmp_path / "clip.preprocessed.wav"),
    ]]


def test_preprocess_audio_reuses_existing_cached_wav(monkeypatch, tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")
    cached = tmp_path / "clip.preprocessed.wav"
    cached.write_bytes(b"processed")

    def fail_run(*args, **kwargs) -> None:
        raise AssertionError("ffmpeg should not run when cache exists")

    monkeypatch.setattr(subprocess, "run", fail_run)

    assert preprocess_audio(str(source)) == str(cached)
