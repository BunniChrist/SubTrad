from pathlib import Path

from backend.audio_preprocess import build_preprocessed_audio_path


def test_build_preprocessed_audio_path_uses_stable_cache_name(tmp_path) -> None:
    source = tmp_path / "clip.m4a"
    source.write_bytes(b"audio")

    path = build_preprocessed_audio_path(source)

    assert path == tmp_path / "clip.preprocessed.wav"
