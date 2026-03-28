from types import SimpleNamespace

import pytest

from backend.services.transcriber import transcribe_audio, transcribe_audio_with_metadata


class FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class FakeInfo:
    def __init__(self, language: str | None) -> None:
        self.language = language


class FakeWhisperModel:
    init_calls: list[tuple[str, str, str]] = []

    def __init__(self, model_name: str, device: str, compute_type: str) -> None:
        type(self).init_calls.append((model_name, device, compute_type))

    def transcribe(self, audio_path: str, word_timestamps: bool = False):
        assert audio_path
        assert word_timestamps is False
        segments = [
            FakeSegment(0.0, 1.25, "Bonjour"),
            FakeSegment(1.25, 2.5, "le monde"),
        ]
        return iter(segments), FakeInfo("fr")


class ErroringWhisperModel:
    def transcribe(self, audio_path: str, word_timestamps: bool = False):
        raise RuntimeError("decode failed")


def test_get_model_returns_singleton_instance(monkeypatch) -> None:
    from backend.services import transcriber

    FakeWhisperModel.init_calls = []
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)

    first = transcriber._get_model()
    second = transcriber._get_model()

    assert first is second
    assert FakeWhisperModel.init_calls == [("distil-test-model", "cpu", "int8")]


def test_transcribe_audio_parses_distil_whisper_segments(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    FakeWhisperModel.init_calls = []
    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)

    segments = transcribe_audio(str(audio_file))

    assert segments == [
        {"start": 0.0, "end": 1.25, "text": "Bonjour"},
        {"start": 1.25, "end": 2.5, "text": "le monde"},
    ]


def test_transcribe_audio_returns_empty_list_for_empty_audio(tmp_path) -> None:
    empty_audio = tmp_path / "empty.mp3"
    empty_audio.write_bytes(b"")

    assert transcribe_audio(str(empty_audio)) == []


def test_transcribe_audio_with_metadata_returns_empty_payload_for_missing_file(tmp_path) -> None:
    missing_audio = tmp_path / "missing.mp3"

    assert transcribe_audio_with_metadata(str(missing_audio)) == {
        "segments": [],
        "language": None,
    }


def test_transcribe_audio_rejects_unsupported_extensions(tmp_path) -> None:
    audio_file = tmp_path / "audio.aac"
    audio_file.write_bytes(b"fake-audio" * 256)

    with pytest.raises(ValueError, match="Unsupported audio format"):
        transcribe_audio(str(audio_file))


def test_transcribe_audio_rejects_tiny_files(tmp_path) -> None:
    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"tiny")

    with pytest.raises(ValueError, match="Audio file too small"):
        transcribe_audio(str(audio_file))


def test_transcribe_audio_raises_value_error_for_invalid_audio(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    monkeypatch.setattr(transcriber, "_get_model", lambda: ErroringWhisperModel())

    with pytest.raises(ValueError, match="Invalid audio file"):
        transcribe_audio(str(audio_file))


def test_transcribe_audio_returns_float_timestamps(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)

    segments = transcribe_audio(str(audio_file))

    assert isinstance(segments[0]["start"], float)
    assert isinstance(segments[0]["end"], float)


def test_transcribe_audio_with_metadata_returns_detected_language(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)

    payload = transcribe_audio_with_metadata(str(audio_file))

    assert payload == {
        "segments": [
            {"start": 0.0, "end": 1.25, "text": "Bonjour"},
            {"start": 1.25, "end": 2.5, "text": "le monde"},
        ],
        "language": "fr",
    }
