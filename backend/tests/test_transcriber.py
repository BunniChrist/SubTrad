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

    def transcribe(self, audio_path: str, word_timestamps: bool = False, **kwargs):
        assert audio_path
        assert word_timestamps is False
        segments = [
            FakeSegment(0.0, 1.25, "Bonjour"),
            FakeSegment(1.25, 2.5, "le monde"),
        ]
        return iter(segments), FakeInfo("fr")


class ErroringWhisperModel:
    def transcribe(self, audio_path: str, word_timestamps: bool = False, **kwargs):
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
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))

    segments = transcribe_audio(str(audio_file))

    assert segments == [{"start": 0.0, "end": 2.5, "text": "Bonjour le monde"}]


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
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    monkeypatch.setattr(transcriber, "_get_model", lambda: ErroringWhisperModel())
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))

    with pytest.raises(ValueError, match="Invalid audio file"):
        transcribe_audio(str(audio_file))


def test_transcribe_audio_returns_float_timestamps(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))

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
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    monkeypatch.setattr(
        transcriber,
        "get_settings",
        lambda: SimpleNamespace(whisper_model="distil-test-model"),
    )
    monkeypatch.setattr(transcriber, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(transcriber, "_model", None)
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))

    payload = transcribe_audio_with_metadata(str(audio_file))

    assert payload == {
        "segments": [{"start": 0.0, "end": 2.5, "text": "Bonjour le monde"}],
        "language": "fr",
        "timings": {"preprocess_seconds": 0.0, "transcription_seconds": 0.0},
    }


def test_transcribe_audio_uses_preprocessed_audio(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    seen_paths: list[str] = []

    class RecordingModel:
        def transcribe(self, audio_path: str, **kwargs):
            seen_paths.append(audio_path)
            return iter([FakeSegment(0.0, 1.0, "Hello")]), FakeInfo("en")

    monkeypatch.setattr(transcriber, "_get_model", lambda: RecordingModel())
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))
    monkeypatch.setattr(transcriber, "cleanup_transcript", lambda segments: segments)

    payload = transcribe_audio_with_metadata(str(audio_file), source_lang="en")

    assert payload["segments"] == [{"start": 0.0, "end": 1.0, "text": "Hello"}]
    assert seen_paths == [str(preprocessed_file)]


def test_transcribe_audio_detects_language_from_first_thirty_seconds_when_unspecified(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    calls: list[dict[str, object]] = []

    class DetectingModel:
        def transcribe(self, audio_path: str, **kwargs):
            calls.append({"audio_path": audio_path, **kwargs})
            if len(calls) == 1:
                return iter([FakeSegment(0.0, 1.0, "hello")]), FakeInfo("es")
            return iter([FakeSegment(0.0, 1.0, "hola")]), FakeInfo("es")

    monkeypatch.setattr(transcriber, "_get_model", lambda: DetectingModel())
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))
    monkeypatch.setattr(transcriber, "cleanup_transcript", lambda segments: segments)

    payload = transcribe_audio_with_metadata(str(audio_file))

    assert payload["language"] == "es"
    assert calls == [
        {"audio_path": str(preprocessed_file), "word_timestamps": False, "vad_filter": True, "clip_timestamps": "0,30"},
        {"audio_path": str(preprocessed_file), "word_timestamps": False, "vad_filter": True, "language": "es"},
    ]


def test_transcribe_audio_cleans_segments_before_returning(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)

    class CleaningModel:
        def transcribe(self, audio_path: str, **kwargs):
            return iter(
                [
                    FakeSegment(0.0, 0.8, "[Music]"),
                    FakeSegment(0.8, 1.5, "Hello"),
                    FakeSegment(1.5, 2.0, "Hello"),
                ]
            ), FakeInfo("en")

    monkeypatch.setattr(transcriber, "_get_model", lambda: CleaningModel())
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))

    payload = transcribe_audio_with_metadata(str(audio_file), source_lang="en")

    assert payload == {
        "segments": [{"start": 0.8, "end": 1.5, "text": "Hello"}],
        "language": "en",
        "timings": {"preprocess_seconds": 0.0, "transcription_seconds": 0.0},
    }


def test_transcribe_audio_with_metadata_returns_timing_breakdown(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio" * 256)
    preprocessed_file = tmp_path / "audio.preprocessed.wav"
    preprocessed_file.write_bytes(b"processed-audio" * 256)
    perf_counter_values = iter([10.0, 10.2, 10.2, 10.7])

    class TimingModel:
        def transcribe(self, audio_path: str, **kwargs):
            return iter([FakeSegment(0.0, 1.0, "Hello.")]), FakeInfo("en")

    monkeypatch.setattr(transcriber, "_get_model", lambda: TimingModel())
    monkeypatch.setattr(transcriber, "preprocess_audio", lambda audio_path: str(preprocessed_file))
    monkeypatch.setattr(transcriber.time, "perf_counter", lambda: next(perf_counter_values))

    payload = transcribe_audio_with_metadata(str(audio_file), source_lang="en")

    assert payload["timings"] == {"preprocess_seconds": 0.2, "transcription_seconds": 0.5}
