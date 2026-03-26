from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_root_serves_frontend_index() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SubTrad" in response.text


def test_root_head_returns_frontend_headers() -> None:
    response = client.head("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_frontend_css_asset_is_served() -> None:
    response = client.get("/css/style.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_health_endpoint_returns_ok_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
