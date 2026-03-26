from pathlib import Path

import pytest

from backend.services.transcriber import transcribe_audio


class FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class FakeResponse:
    def __init__(self, segments: list[FakeSegment]) -> None:
        self.segments = segments


class FakeClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.audio = self
        self.transcriptions = self

    def create(self, **kwargs) -> FakeResponse:
        return FakeResponse(
            [
                FakeSegment(0.0, 1.25, "Bonjour"),
                FakeSegment(1.25, 2.5, "le monde"),
            ]
        )


def test_transcribe_audio_parses_whisper_segments(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio")
    monkeypatch.setattr(transcriber, "OpenAI", FakeClient)

    segments = transcribe_audio(str(audio_file), "test-api-key")

    assert segments == [
        {"start": 0.0, "end": 1.25, "text": "Bonjour"},
        {"start": 1.25, "end": 2.5, "text": "le monde"},
    ]


def test_transcribe_audio_returns_empty_list_for_empty_audio(tmp_path) -> None:
    empty_audio = tmp_path / "empty.mp3"
    empty_audio.write_bytes(b"")

    assert transcribe_audio(str(empty_audio), "test-api-key") == []


def test_transcribe_audio_returns_float_timestamps(monkeypatch, tmp_path) -> None:
    from backend.services import transcriber

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"fake-audio")
    monkeypatch.setattr(transcriber, "OpenAI", FakeClient)

    segments = transcribe_audio(str(audio_file), "test-api-key")

    assert isinstance(segments[0]["start"], float)
    assert isinstance(segments[0]["end"], float)


@pytest.mark.integration
def test_transcribe_audio_with_real_whisper_api(monkeypatch) -> None:
    api_key = __import__("os").environ.get("SUBTRAD_OPENAI_API_KEY")
    if not api_key:
        pytest.skip("SUBTRAD_OPENAI_API_KEY is not set")

    fixture_path = Path(__file__).parent / "fixtures" / "test_audio.mp3"
    if not fixture_path.exists():
        pytest.skip("test_audio.mp3 fixture is missing")

    segments = transcribe_audio(str(fixture_path), api_key)

    assert isinstance(segments, list)
    assert all(isinstance(segment["start"], float) for segment in segments)
