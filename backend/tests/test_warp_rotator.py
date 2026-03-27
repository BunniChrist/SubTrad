import httpx

from backend.services.warp_rotator import is_youtube_block, rotate_warp_ip


def test_rotate_warp_ip_returns_true_on_success(monkeypatch) -> None:
    def fake_post(url: str, timeout: float) -> httpx.Response:
        assert url == "http://10.0.1.1:40002/rotate"
        assert timeout == 20.0
        return httpx.Response(
            200,
            json={"status": "rotated", "new_ip": "1.2.3.4"},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    assert rotate_warp_ip("http://10.0.1.1:40002/rotate") is True


def test_rotate_warp_ip_returns_false_on_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, timeout: httpx.Response(
            200,
            json={"status": "cooldown", "seconds_remaining": 20},
        ),
    )

    assert rotate_warp_ip("http://10.0.1.1:40002/rotate") is False


def test_rotate_warp_ip_returns_false_on_error_response(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, timeout: httpx.Response(
            200,
            json={"status": "error", "detail": "warp-cli failed"},
        ),
    )

    assert rotate_warp_ip("http://10.0.1.1:40002/rotate") is False


def test_rotate_warp_ip_returns_false_when_service_is_unreachable(monkeypatch) -> None:
    def fake_post(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    assert rotate_warp_ip("http://10.0.1.1:40002/rotate") is False


def test_is_youtube_block_matches_known_patterns() -> None:
    assert is_youtube_block(Exception("Sign in to confirm you're not a bot")) is True
    assert is_youtube_block(Exception("Some other error")) is False
