from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_root_is_not_served() -> None:
    response = client.get("/")

    assert response.status_code == 404


def test_legal_page_is_not_served() -> None:
    response = client.get("/legal.html")

    assert response.status_code == 404


def test_frontend_css_asset_is_not_served() -> None:
    response = client.get("/css/style.css")

    assert response.status_code == 404


def test_health_endpoint_returns_ok_status() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "deno" in data
