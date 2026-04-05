from __future__ import annotations

import subprocess
from types import SimpleNamespace

from backend.services.translator_codex import (
    detect_source_language_codex,
    translate_subtitles_with_metadata_codex,
)


def make_segments(count: int) -> list[dict[str, float | str]]:
    return [
        {"start": float(index), "end": float(index) + 0.5, "text": f"Line {index}"}
        for index in range(1, count + 1)
    ]


def test_detect_source_language_codex_returns_language_code(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, capture_output, text, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="en\n", stderr="")

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)

    detected = detect_source_language_codex(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "How are you?"},
            {"start": 2.0, "end": 3.0, "text": "Let's go"},
        ]
    )

    assert detected == "en"
    assert calls == [[
        "codex",
        "exec",
        "-m",
        "gpt-4o-mini",
        "What language is this subtitle sample? Reply with the ISO 639-1 code only.\n1|Hello\n2|How are you?\n3|Let's go",
    ]]


def test_translate_subtitles_with_metadata_codex_replaces_text_and_preserves_timestamps(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, capture_output, text, timeout):
        calls.append(args)
        if len(calls) == 1:
            return SimpleNamespace(returncode=0, stdout="en\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="1|Bonjour\n2|Salut\n", stderr="")

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)

    result = translate_subtitles_with_metadata_codex(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "Hi"},
        ],
        "fr",
    )

    assert result.detected_language == "en"
    assert result.translation_status == "translated"
    assert result.segments == [
        {"start": 0.0, "end": 1.0, "text": "Bonjour"},
        {"start": 1.0, "end": 2.0, "text": "Salut"},
    ]
    assert calls[1][:4] == ["codex", "exec", "-m", "gpt-4o-mini"]


def test_translate_subtitles_with_metadata_codex_falls_back_on_timeout(monkeypatch) -> None:
    def fake_run(args, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)
    original_segments = make_segments(2)

    result = translate_subtitles_with_metadata_codex(
        original_segments,
        "fr",
        source_lang="en",
    )

    assert result.detected_language == "en"
    assert result.translation_status == "failed_fallback_original"
    assert result.segments == original_segments


def test_translate_subtitles_with_metadata_codex_falls_back_on_non_zero_exit(monkeypatch) -> None:
    def fake_run(args, capture_output, text, timeout):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)
    original_segments = make_segments(2)

    result = translate_subtitles_with_metadata_codex(
        original_segments,
        "fr",
        source_lang="en",
    )

    assert result.translation_status == "failed_fallback_original"
    assert result.segments == original_segments


def test_translate_subtitles_with_metadata_codex_returns_empty_segments() -> None:
    result = translate_subtitles_with_metadata_codex([], "fr")

    assert result.segments == []
    assert result.detected_language is None
    assert result.translation_status == "translated"


def test_translate_subtitles_with_metadata_codex_skips_same_language(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, capture_output, text, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="unused\n", stderr="")

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)
    original_segments = [{"start": 0.0, "end": 1.0, "text": "Hello"}]

    result = translate_subtitles_with_metadata_codex(
        original_segments,
        "en",
        source_lang="en",
    )

    assert result.translation_status == "skipped_same_lang"
    assert result.segments == original_segments
    assert calls == []
