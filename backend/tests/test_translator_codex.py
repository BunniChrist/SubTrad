from __future__ import annotations

import subprocess
from types import SimpleNamespace

from backend.services.translator_codex import (
    _parse_codex_output,
    detect_source_language_codex,
    translate_subtitles_with_metadata_codex,
)


def make_segments(count: int) -> list[dict[str, float | str]]:
    return [
        {"start": float(index), "end": float(index) + 0.5, "text": f"Line {index}"}
        for index in range(1, count + 1)
    ]


def _codex_stdout(response: str) -> str:
    return f"codex\n{response}\ntokens used\n100\n{response}"


def test_detect_source_language_codex_returns_language_code(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_run(args, capture_output, text, timeout, input=None):
        calls.append({"args": args, "input": input})
        return SimpleNamespace(returncode=0, stdout=_codex_stdout("en"), stderr="")

    monkeypatch.setattr("backend.services.translator_codex.subprocess.run", fake_run)

    detected = detect_source_language_codex(
        [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.0, "end": 2.0, "text": "How are you?"},
            {"start": 2.0, "end": 3.0, "text": "Let's go"},
        ]
    )

    assert detected == "en"
    assert calls[0]["args"] == [
        "codex", "exec", "--skip-git-repo-check", "-m", "gpt-4o-mini", "-",
    ]
    assert "Hello" in calls[0]["input"]


def test_translate_subtitles_with_metadata_codex_replaces_text_and_preserves_timestamps(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_run(args, capture_output, text, timeout, input=None):
        calls.append({"args": args, "input": input, "timeout": timeout})
        if len(calls) == 1:
            return SimpleNamespace(returncode=0, stdout=_codex_stdout("en"), stderr="")
        return SimpleNamespace(returncode=0, stdout=_codex_stdout("1|Bonjour\n2|Salut"), stderr="")

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
    assert calls[1]["args"][:4] == ["codex", "exec", "--skip-git-repo-check", "-m"]
    assert calls[1]["timeout"] == 900


def test_translate_subtitles_with_metadata_codex_falls_back_on_timeout(monkeypatch) -> None:
    def fake_run(args, capture_output, text, timeout, input=None):
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
    def fake_run(args, capture_output, text, timeout, input=None):
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
    calls: list[dict] = []

    def fake_run(args, capture_output, text, timeout, input=None):
        calls.append({"args": args})
        return SimpleNamespace(returncode=0, stdout=_codex_stdout("unused"), stderr="")

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


def test_parse_codex_output_extracts_response() -> None:
    raw = "codex\n1|Bonjour\n2|Salut\ntokens used\n1394\n1|Bonjour\n2|Salut"
    assert _parse_codex_output(raw) == "1|Bonjour\n2|Salut"


def test_parse_codex_output_deduplicates_before_tokens_used() -> None:
    raw = "codex\n1|Bonjour\n2|Salut\n1|Bonjour\n2|Salut\ntokens used\n8584"
    assert _parse_codex_output(raw) == "1|Bonjour\n2|Salut"


def test_parse_codex_output_handles_plain_text() -> None:
    assert _parse_codex_output("just plain text") == "just plain text"


def test_parse_codex_output_handles_empty() -> None:
    assert _parse_codex_output("") is None
