import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
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
    assert len(commands) == 1
    assert commands[0][:-1] == [
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
    ]
    assert commands[0][-1].startswith(str(tmp_path / "clip.preprocessed."))
    assert commands[0][-1].endswith(".tmp.wav")


def test_preprocess_audio_reuses_existing_cached_wav(monkeypatch, tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")
    cached = tmp_path / "clip.preprocessed.wav"
    cached.write_bytes(b"processed")

    def fail_run(*args, **kwargs) -> None:
        raise AssertionError("ffmpeg should not run when cache exists")

    monkeypatch.setattr(subprocess, "run", fail_run)

    assert preprocess_audio(str(source)) == str(cached)


def test_preprocess_audio_writes_via_temp_file_before_promoting(monkeypatch, tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")
    command_targets: list[str] = []

    def fake_run(command: list[str], check: bool, capture_output: bool) -> None:
        command_targets.append(command[-1])
        Path(command[-1]).write_bytes(b"processed")
        time.sleep(0.05)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: preprocess_audio(str(source)), range(2)))

    final_output = tmp_path / "clip.preprocessed.wav"
    assert results == [str(final_output), str(final_output)]
    assert all(target != str(final_output) for target in command_targets)
    assert final_output.read_bytes() == b"processed"
    assert not any(tmp_path.glob("clip.preprocessed.*.tmp.wav"))


def test_preprocess_audio_surfaces_ffmpeg_stderr(monkeypatch, tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")

    def fake_run(command: list[str], check: bool, capture_output: bool) -> None:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            stderr=b"Invalid data found when processing input",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        preprocess_audio(str(source))
    except ValueError as exc:
        assert "Audio preprocessing failed:" in str(exc)
        assert "Invalid data found when processing input" in str(exc)
    else:  # pragma: no cover - test should fail before this branch
        raise AssertionError("preprocess_audio should raise ValueError on ffmpeg failure")
