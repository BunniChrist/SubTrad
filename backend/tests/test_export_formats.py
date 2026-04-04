from backend.export_formats import to_md, to_txt, to_vtt


def test_to_vtt_renders_webvtt_segments() -> None:
    payload = to_vtt(
        [
            {"start": 0.0, "end": 1.5, "text": "Hello"},
            {"start": 30.0, "end": 33.25, "text": "World & more"},
        ]
    )

    assert payload == (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.500\n"
        "Hello\n\n"
        "00:00:30.000 --> 00:00:33.250\n"
        "World & more\n"
    )


def test_to_txt_joins_non_empty_segments() -> None:
    payload = to_txt(
        [
            {"start": 0.0, "end": 1.5, "text": " Hello "},
            {"start": 1.5, "end": 3.0, "text": ""},
            {"start": 3.0, "end": 4.5, "text": "monde"},
        ]
    )

    assert payload == "Hello\nmonde"


def test_to_md_renders_metadata_and_timestamp_markers() -> None:
    payload = to_md(
        [
            {"start": 0.0, "end": 1.5, "text": "Intro"},
            {"start": 31.0, "end": 32.0, "text": "Suite spéciale: café & crème"},
        ],
        metadata={
            "title": "Clip test",
            "platform": "instagram",
            "video_id": "abc123",
            "language": "en",
            "date": "2026-04-04",
        },
    )

    assert payload == (
        "---\n"
        "title: Clip test\n"
        "platform: instagram\n"
        "video_id: abc123\n"
        "language: en\n"
        "date: 2026-04-04\n"
        "---\n\n"
        "[00:00] Intro\n\n"
        "[00:30] Suite spéciale: café & crème"
    )


def test_export_formats_return_empty_outputs_for_empty_segments() -> None:
    assert to_vtt([]) == "WEBVTT\n"
    assert to_txt([]) == ""
    assert to_md([], metadata={"platform": "tiktok"}) == (
        "---\nplatform: tiktok\n---\n"
    )


def test_export_formats_preserve_special_characters_and_emoji() -> None:
    segments = [{"start": 0.0, "end": 1.5, "text": "Cafe deja vu ☕️🔥"}]

    assert to_vtt(segments) == (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.500\n"
        "Cafe deja vu ☕️🔥\n"
    )
    assert to_txt(segments) == "Cafe deja vu ☕️🔥"
    assert "Cafe deja vu ☕️🔥" in to_md(segments, metadata={"platform": "instagram"})
