from backend.services.translation_prompts import (
    get_translation_prompt,
    parse_translation_response,
)


def test_get_translation_prompt_includes_target_language_name() -> None:
    prompt = get_translation_prompt("fr", [{"start": 0.0, "end": 1.0, "text": "Hello"}])

    assert "French" in prompt
    assert "fr" not in prompt


def test_get_translation_prompt_formats_segments_in_numbered_lines() -> None:
    prompt = get_translation_prompt(
        "ja",
        [
            {"start": 0.0, "end": 1.0, "text": "Hello world"},
            {"start": 1.0, "end": 2.0, "text": "How are you today?"},
        ],
    )

    assert "1|Hello world" in prompt
    assert "2|How are you today?" in prompt


def test_parse_translation_response_maps_text_back_to_original_timestamps() -> None:
    original_segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello world"},
        {"start": 1.0, "end": 2.5, "text": "How are you today?"},
    ]

    translated = parse_translation_response(
        "1|Bonjour le monde\n2|Comment vas-tu aujourd'hui ?",
        original_segments,
    )

    assert translated == [
        {"start": 0.0, "end": 1.0, "text": "Bonjour le monde"},
        {"start": 1.0, "end": 2.5, "text": "Comment vas-tu aujourd'hui ?"},
    ]


def test_parse_translation_response_falls_back_to_original_text_on_line_mismatch() -> None:
    original_segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello world"},
        {"start": 1.0, "end": 2.5, "text": "How are you today?"},
    ]

    translated = parse_translation_response("1|Bonjour le monde", original_segments)

    assert translated == original_segments


def test_parse_translation_response_returns_empty_list_for_empty_segments() -> None:
    assert parse_translation_response("1|Bonjour", []) == []
