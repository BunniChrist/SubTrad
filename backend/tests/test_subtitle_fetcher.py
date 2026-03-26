from backend.services.subtitle_fetcher import parse_srt


def test_parse_srt_returns_structured_entries() -> None:
    srt_content = """1
00:00:01,000 --> 00:00:02,500
Bonjour

2
00:00:03,000 --> 00:00:04,000
Salut
"""

    assert parse_srt(srt_content) == [
        {"start": "00:00:01,000", "end": "00:00:02,500", "text": "Bonjour"},
        {"start": "00:00:03,000", "end": "00:00:04,000", "text": "Salut"},
    ]


def test_parse_srt_returns_empty_list_for_empty_input() -> None:
    assert parse_srt("") == []


def test_parse_srt_keeps_multiline_subtitles_in_one_entry() -> None:
    srt_content = """1
00:00:05,000 --> 00:00:07,000
Bonjour
le monde
"""

    assert parse_srt(srt_content) == [
        {
            "start": "00:00:05,000",
            "end": "00:00:07,000",
            "text": "Bonjour le monde",
        }
    ]
