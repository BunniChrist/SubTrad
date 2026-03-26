from __future__ import annotations

import os

import pytest

from backend.services.translator import detect_source_language, translate_subtitles


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class RecordingClient:
    response_queue: list[str] = []
    captured_calls: list[dict] = []

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.chat = self
        self.completions = self

    def create(self, **kwargs) -> FakeResponse:
        self.__class__.captured_calls.append(kwargs)
        content = self.__class__.response_queue.pop(0)
        return FakeResponse(content)


class ErroringClient(RecordingClient):
    def create(self, **kwargs) -> FakeResponse:
        raise RuntimeError("OpenAI unavailable")


def make_segments(count: int) -> list[dict[str, float | str]]:
    return [
        {"start": float(index), "end": float(index) + 0.5, "text": f"Line {index}"}
        for index in range(1, count + 1)
    ]


def test_translate_subtitles_replaces_text_and_preserves_timestamps(monkeypatch) -> None:
    from backend.services import translator

    RecordingClient.response_queue = ["en", "1|Bonjour\n2|Salut"]
    RecordingClient.captured_calls = []
    monkeypatch.setattr(translator, "OpenAI", RecordingClient)

    translated = translate_subtitles(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "Hi"},
        ],
        "fr",
        "test-api-key",
    )

    assert translated == [
        {"start": 0.0, "end": 1.0, "text": "Bonjour"},
        {"start": 1.0, "end": 2.0, "text": "Salut"},
    ]


def test_translate_subtitles_returns_empty_list_for_empty_segments() -> None:
    assert translate_subtitles([], "fr", "test-api-key") == []


def test_translate_subtitles_skips_when_source_matches_target(monkeypatch) -> None:
    from backend.services import translator

    RecordingClient.response_queue = []
    RecordingClient.captured_calls = []
    monkeypatch.setattr(translator, "OpenAI", RecordingClient)

    original_segments = [{"start": 0.0, "end": 1.0, "text": "Hello"}]
    translated = translate_subtitles(
        original_segments,
        "en",
        "test-api-key",
        source_lang="en",
    )

    assert translated == original_segments
    assert RecordingClient.captured_calls == []


def test_translate_subtitles_batches_requests_in_groups_of_twenty(monkeypatch) -> None:
    from backend.services import translator

    RecordingClient.response_queue = [
        "1|Ligne 1\n2|Ligne 2\n3|Ligne 3\n4|Ligne 4\n5|Ligne 5\n6|Ligne 6\n7|Ligne 7\n8|Ligne 8\n9|Ligne 9\n10|Ligne 10\n11|Ligne 11\n12|Ligne 12\n13|Ligne 13\n14|Ligne 14\n15|Ligne 15\n16|Ligne 16\n17|Ligne 17\n18|Ligne 18\n19|Ligne 19\n20|Ligne 20",
        "1|Ligne 21\n2|Ligne 22\n3|Ligne 23\n4|Ligne 24\n5|Ligne 25\n6|Ligne 26\n7|Ligne 27\n8|Ligne 28\n9|Ligne 29\n10|Ligne 30\n11|Ligne 31\n12|Ligne 32\n13|Ligne 33\n14|Ligne 34\n15|Ligne 35\n16|Ligne 36\n17|Ligne 37\n18|Ligne 38\n19|Ligne 39\n20|Ligne 40",
        "1|Ligne 41\n2|Ligne 42\n3|Ligne 43\n4|Ligne 44\n5|Ligne 45\n6|Ligne 46\n7|Ligne 47\n8|Ligne 48\n9|Ligne 49\n10|Ligne 50",
    ]
    RecordingClient.captured_calls = []
    monkeypatch.setattr(translator, "OpenAI", RecordingClient)

    translated = translate_subtitles(
        make_segments(50),
        "fr",
        "test-api-key",
        source_lang="en",
    )

    assert len(RecordingClient.captured_calls) == 3
    assert [segment["text"] for segment in translated[:3]] == [
        "Ligne 1",
        "Ligne 2",
        "Ligne 3",
    ]
    assert translated[-1]["text"] == "Ligne 50"


def test_translate_subtitles_returns_original_batch_when_api_fails(monkeypatch) -> None:
    from backend.services import translator

    monkeypatch.setattr(translator, "OpenAI", ErroringClient)
    original_segments = make_segments(2)

    translated = translate_subtitles(
        original_segments,
        "fr",
        "test-api-key",
        source_lang="en",
    )

    assert translated == original_segments


def test_detect_source_language_returns_language_code(monkeypatch) -> None:
    from backend.services import translator

    RecordingClient.response_queue = ["en"]
    RecordingClient.captured_calls = []
    monkeypatch.setattr(translator, "OpenAI", RecordingClient)

    detected = detect_source_language(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "How are you?"},
            {"start": 2.0, "end": 3.0, "text": "Let's go"},
        ],
        "test-api-key",
    )

    assert detected == "en"


@pytest.mark.integration
def test_translate_subtitles_with_real_openai_api() -> None:
    api_key = os.environ.get("SUBTRAD_OPENAI_API_KEY")
    if not api_key:
        pytest.skip("SUBTRAD_OPENAI_API_KEY is not set")

    translated = translate_subtitles(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello everyone"},
            {"start": 1.0, "end": 2.0, "text": "This is a short test"},
            {"start": 2.0, "end": 3.0, "text": "See you soon"},
        ],
        "fr",
        api_key,
    )

    assert len(translated) == 3
    assert all(segment["text"] for segment in translated)
    assert translated[0]["start"] == 0.0
