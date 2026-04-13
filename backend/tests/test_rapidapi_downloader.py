from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.rapidapi_downloader import extract_audio_via_rapidapi


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: object | None = None,
        content: bytes = b"",
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self._chunks = chunks if chunks is not None else [content]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload

    def iter_content(self, chunk_size: int = 8192):
        yield from self._chunks


def test_extract_audio_via_rapidapi_uses_first_host_when_success(monkeypatch, tmp_path) -> None:
    from backend.services import rapidapi_downloader

    calls: list[tuple[str, str]] = []

    def fake_get(url, *, headers=None, params=None, timeout=None, stream=False):
        host = headers.get("X-RapidAPI-Host", "") if headers else ""
        calls.append((host, url))
        if not stream:
            return FakeResponse(payload={"downloadUrl": "https://cdn.example/audio1.m4a"})
        return FakeResponse(chunks=[b"audio", b"-bytes"])

    monkeypatch.setattr(
        rapidapi_downloader,
        "get_settings",
        lambda: SimpleNamespace(
            rapidapi_key="rapidapi-key",
            rapidapi_host_1="host-1",
            rapidapi_host_2="host-2",
            rapidapi_host_3="host-3",
        ),
    )
    monkeypatch.setattr(rapidapi_downloader, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(rapidapi_downloader.requests, "get", fake_get)

    audio_path = extract_audio_via_rapidapi("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert audio_path.endswith(".m4a")
    assert (tmp_path / audio_path.split("/")[-1]).exists()
    assert calls[0][0] == "host-1"


def test_extract_audio_via_rapidapi_falls_back_to_host_2(monkeypatch, tmp_path) -> None:
    from backend.services import rapidapi_downloader

    metadata_hosts: list[str] = []

    def fake_get(url, *, headers=None, params=None, timeout=None, stream=False):
        host = headers.get("X-RapidAPI-Host", "") if headers else ""
        if stream:
            return FakeResponse(chunks=[b"host2-audio"])

        metadata_hosts.append(host)
        if host == "host-1":
            return FakeResponse(status_code=503, payload={"error": "unavailable"})
        return FakeResponse(payload={"data": {"url": "https://cdn.example/audio2.mp3"}})

    monkeypatch.setattr(
        rapidapi_downloader,
        "get_settings",
        lambda: SimpleNamespace(
            rapidapi_key="rapidapi-key",
            rapidapi_host_1="host-1",
            rapidapi_host_2="host-2",
            rapidapi_host_3="host-3",
        ),
    )
    monkeypatch.setattr(rapidapi_downloader, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(rapidapi_downloader.requests, "get", fake_get)

    audio_path = extract_audio_via_rapidapi("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert audio_path.endswith(".mp3")
    assert metadata_hosts[:2] == ["host-1", "host-2"]


def test_extract_audio_via_rapidapi_raises_when_all_hosts_fail(monkeypatch, tmp_path) -> None:
    from backend.services import rapidapi_downloader

    metadata_hosts: list[str] = []

    def fake_get(url, *, headers=None, params=None, timeout=None, stream=False):
        if stream:
            return FakeResponse(chunks=[])
        host = headers.get("X-RapidAPI-Host", "") if headers else ""
        metadata_hosts.append(host)
        return FakeResponse(status_code=500, payload={"error": "failed"})

    monkeypatch.setattr(
        rapidapi_downloader,
        "get_settings",
        lambda: SimpleNamespace(
            rapidapi_key="rapidapi-key",
            rapidapi_host_1="host-1",
            rapidapi_host_2="host-2",
            rapidapi_host_3="host-3",
        ),
    )
    monkeypatch.setattr(rapidapi_downloader, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(rapidapi_downloader.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="All RapidAPI download hosts failed"):
        extract_audio_via_rapidapi("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert metadata_hosts == ["host-1", "host-2", "host-3"]


@pytest.mark.parametrize(
    ("host", "expected_path"),
    [
        ("youtube-media-downloader.p.rapidapi.com", "/v2/video/details"),
        ("youtube-search-and-download.p.rapidapi.com", "/video/download"),
        ("cloud-api-hub-youtube-downloader.p.rapidapi.com", "/download"),
    ],
)
def test_extract_audio_via_rapidapi_uses_host_specific_endpoint(
    monkeypatch, tmp_path, host: str, expected_path: str
) -> None:
    from backend.services import rapidapi_downloader

    called_urls: list[str] = []

    def fake_get(url, *, headers=None, params=None, timeout=None, stream=False):
        called_urls.append(url)
        if not stream:
            return FakeResponse(
                payload={
                    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                    "url": "https://redirector.googlevideo.com/videoplayback?mime=audio/mp4",
                }
            )
        return FakeResponse(chunks=[b"audio-bytes"])

    monkeypatch.setattr(
        rapidapi_downloader,
        "get_settings",
        lambda: SimpleNamespace(
            rapidapi_key="rapidapi-key",
            rapidapi_host_1=host,
            rapidapi_host_2="",
            rapidapi_host_3="",
        ),
    )
    monkeypatch.setattr(rapidapi_downloader, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(rapidapi_downloader.requests, "get", fake_get)

    audio_path = extract_audio_via_rapidapi("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert audio_path.endswith(".m4a")
    assert expected_path in called_urls[0]


def test_extract_audio_via_rapidapi_ignores_thumbnail_urls(monkeypatch, tmp_path) -> None:
    from backend.services import rapidapi_downloader

    def fake_get(url, *, headers=None, params=None, timeout=None, stream=False):
        if not stream:
            return FakeResponse(
                payload={
                    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                    "medias": [
                        {"mimeType": "audio/mp4", "url": "https://redirector.googlevideo.com/videoplayback?mime=audio/mp4"}
                    ],
                }
            )
        assert "googlevideo.com/videoplayback" in url
        return FakeResponse(chunks=[b"audio-content"])

    monkeypatch.setattr(
        rapidapi_downloader,
        "get_settings",
        lambda: SimpleNamespace(
            rapidapi_key="rapidapi-key",
            rapidapi_host_1="youtube-search-and-download.p.rapidapi.com",
            rapidapi_host_2="",
            rapidapi_host_3="",
        ),
    )
    monkeypatch.setattr(rapidapi_downloader, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(rapidapi_downloader.requests, "get", fake_get)

    audio_path = extract_audio_via_rapidapi("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert audio_path.endswith(".m4a")
