from backend.services.subtitle_fetcher import fetch_existing_subtitles, parse_srt


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


def test_fetch_existing_subtitles_passes_cookie_file_and_proxy(monkeypatch) -> None:
    captured_options: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def extract_info(self, url: str, download: bool = False) -> dict[str, object]:
            return {
                "automatic_captions": {
                    "en": [{"ext": "srv3", "url": "https://example.com/captions.srv3"}]
                }
            }

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)

    class FakeResponse:
        status_code = 200
        text = '<transcript><text start="1" dur="1.5">Hello world</text></transcript>'

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeResponse())

    result = fetch_existing_subtitles(
        "https://www.youtube.com/watch?v=abc123",
        proxy="http://proxy.test",
        cookie_file="/tmp/cookies.txt",
    )

    assert result == [{
        "start": "1.000",
        "end": "2.500",
        "text": "Hello world",
    }]
    assert captured_options["proxy"] == "http://proxy.test"
    assert captured_options["cookiefile"] == "/tmp/cookies.txt"
