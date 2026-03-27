from pathlib import Path
from types import SimpleNamespace

import backend.services.subtitle_fetcher as subtitle_fetcher
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


def test_fetch_existing_subtitles_passes_cookie_file_and_proxy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_options: dict[str, object] = {}
    captured_urls: list[str] = []
    temp_dir = tmp_path / "downloaded-subs"
    temp_dir.mkdir()

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            captured_urls.extend(urls)
            (temp_dir / "fetch-existing-subtitles.en.srv3").write_text(
                '<transcript><text start="1" dur="1.5">Hello world</text></transcript>',
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        subtitle_fetcher,
        "tempfile",
        SimpleNamespace(mkdtemp=lambda prefix=None: str(temp_dir)),
        raising=False,
    )
    monkeypatch.setattr(
        subtitle_fetcher.shutil,
        "rmtree",
        lambda path, ignore_errors=True: None,
    )

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
    assert captured_urls == ["https://www.youtube.com/watch?v=abc123"]
    assert captured_options["proxy"] == "http://proxy.test"
    assert captured_options["cookiefile"] == "/tmp/cookies.txt"


def test_fetch_existing_subtitles_downloads_and_cleans_up_srv3_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_options: dict[str, object] = {}
    captured_urls: list[str] = []
    temp_dir = tmp_path / "yt-dlp-subs"
    temp_dir.mkdir()

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            captured_urls.extend(urls)
            subtitle_file = temp_dir / "abc123.en.srv3"
            subtitle_file.write_text(
                '<transcript><text start="1" dur="1.5">Hello world</text></transcript>',
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        subtitle_fetcher,
        "tempfile",
        SimpleNamespace(mkdtemp=lambda prefix=None: str(temp_dir)),
        raising=False,
    )

    result = fetch_existing_subtitles(
        "https://www.youtube.com/watch?v=abc123",
        proxy="socks5h://10.0.1.1:40001",
        cookie_file="/root/yt_cookies.txt",
    )

    assert result == [{
        "start": "1.000",
        "end": "2.500",
        "text": "Hello world",
    }]
    assert captured_urls == ["https://www.youtube.com/watch?v=abc123"]
    assert captured_options["proxy"] == "socks5h://10.0.1.1:40001"
    assert captured_options["cookiefile"] == "/root/yt_cookies.txt"
    assert captured_options["writesubtitles"] is True
    assert captured_options["writeautomaticsub"] is True
    assert captured_options["subtitlesformat"] == "srv3"
    assert captured_options["subtitleslangs"] == ["all"]
    assert captured_options["extractor_args"] == {
        "youtube": {"player_client": ["web", "default"]}
    }
    assert not temp_dir.exists()


def test_fetch_existing_subtitles_uses_downloaded_srv3_even_if_ytdlp_raises(
    monkeypatch,
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "partial-download"
    temp_dir.mkdir()

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.options = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            (temp_dir / "abc123.en.srv3").write_text(
                '<transcript><text start="1" dur="1.5">Hello world</text></transcript>',
                encoding="utf-8",
            )
            raise Exception("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        subtitle_fetcher,
        "tempfile",
        SimpleNamespace(mkdtemp=lambda prefix=None: str(temp_dir)),
        raising=False,
    )

    result = fetch_existing_subtitles("https://www.youtube.com/watch?v=abc123")

    assert result == [{
        "start": "1.000",
        "end": "2.500",
        "text": "Hello world",
    }]
    assert not temp_dir.exists()


def test_fetch_existing_subtitles_retries_after_rotation(monkeypatch, tmp_path: Path) -> None:
    temp_dir = tmp_path / "retry-after-rotation"
    temp_dir.mkdir()
    download_attempts: list[list[str]] = []
    rotation_calls: list[str] = []

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.options = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            download_attempts.append(list(urls))
            if len(download_attempts) == 1:
                raise Exception("Sign in to confirm you're not a bot")
            (temp_dir / "abc123.en.srv3").write_text(
                '<transcript><text start="1" dur="1.5">Hello world</text></transcript>',
                encoding="utf-8",
            )

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        subtitle_fetcher,
        "tempfile",
        SimpleNamespace(mkdtemp=lambda prefix=None: str(temp_dir)),
        raising=False,
    )
    monkeypatch.setattr(
        subtitle_fetcher.shutil,
        "rmtree",
        lambda path, ignore_errors=True: None,
    )
    monkeypatch.setattr(
        subtitle_fetcher,
        "rotate_warp_ip",
        lambda url: rotation_calls.append(url) or True,
    )
    monkeypatch.setattr(
        subtitle_fetcher,
        "get_settings",
        lambda: SimpleNamespace(warp_rotation_url="http://10.0.1.1:40002/rotate"),
    )

    result = fetch_existing_subtitles("https://www.youtube.com/watch?v=abc123")

    assert result == [{
        "start": "1.000",
        "end": "2.500",
        "text": "Hello world",
    }]
    assert download_attempts == [
        ["https://www.youtube.com/watch?v=abc123"],
        ["https://www.youtube.com/watch?v=abc123"],
    ]
    assert rotation_calls == ["http://10.0.1.1:40002/rotate"]


def test_fetch_existing_subtitles_does_not_retry_without_rotation_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "no-rotation-url"
    temp_dir.mkdir()
    rotation_calls: list[str] = []

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.options = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            raise Exception("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr("backend.services.subtitle_fetcher.YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        subtitle_fetcher,
        "tempfile",
        SimpleNamespace(mkdtemp=lambda prefix=None: str(temp_dir)),
        raising=False,
    )
    monkeypatch.setattr(
        subtitle_fetcher.shutil,
        "rmtree",
        lambda path, ignore_errors=True: None,
    )
    monkeypatch.setattr(
        subtitle_fetcher,
        "rotate_warp_ip",
        lambda url: rotation_calls.append(url) or True,
    )
    monkeypatch.setattr(
        subtitle_fetcher,
        "get_settings",
        lambda: SimpleNamespace(warp_rotation_url=""),
    )

    assert fetch_existing_subtitles("https://www.youtube.com/watch?v=abc123") is None
    assert rotation_calls == []
