from fastapi.testclient import TestClient

from backend.main import app
from backend.services.lead_store import LeadStore


client = TestClient(app)


def test_create_premium_lead_returns_created_response(monkeypatch) -> None:
    from backend.routers import leads

    class FakeLeadStore:
        def save_lead(self, email: str, lead_type: str, message: str | None = None) -> int:
            assert email == "user@example.com"
            assert lead_type == "premium"
            assert message is None
            return 1

        def get_lead_count(self, lead_type: str) -> int:
            assert lead_type == "premium"
            return 42

        def lead_exists(self, email: str, lead_type: str) -> bool:
            return False

    monkeypatch.setattr(leads, "lead_store", FakeLeadStore())

    response = client.post(
        "/api/leads",
        json={"email": "user@example.com", "type": "premium"},
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok", "lead_id": 1, "total_signups": 42}


def test_create_suggestion_lead_returns_created_response(monkeypatch) -> None:
    from backend.routers import leads

    class FakeLeadStore:
        def save_lead(self, email: str, lead_type: str, message: str | None = None) -> int:
            assert message == "Add more subtitle formats"
            return 7

        def get_lead_count(self, lead_type: str) -> int:
            return 3

        def lead_exists(self, email: str, lead_type: str) -> bool:
            return False

    monkeypatch.setattr(leads, "lead_store", FakeLeadStore())

    response = client.post(
        "/api/leads",
        json={
            "email": "user@example.com",
            "type": "suggestion",
            "message": "Add more subtitle formats",
        },
    )

    assert response.status_code == 201
    assert response.json() == {"status": "ok", "lead_id": 7, "total_signups": 3}


def test_create_lead_rejects_invalid_email() -> None:
    response = client.post(
        "/api/leads",
        json={"email": "not-an-email", "type": "premium"},
    )

    assert response.status_code == 422


def test_create_lead_rejects_invalid_type() -> None:
    response = client.post(
        "/api/leads",
        json={"email": "user@example.com", "type": "vip"},
    )

    assert response.status_code == 422


def test_duplicate_email_returns_already_registered(monkeypatch) -> None:
    from backend.routers import leads

    class FakeLeadStore:
        def save_lead(self, email: str, lead_type: str, message: str | None = None) -> int:
            raise AssertionError("save_lead should not be called for duplicates")

        def get_lead_count(self, lead_type: str) -> int:
            return 42

        def lead_exists(self, email: str, lead_type: str) -> bool:
            return True

    monkeypatch.setattr(leads, "lead_store", FakeLeadStore())

    response = client.post(
        "/api/leads",
        json={"email": "user@example.com", "type": "premium"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "already_registered", "total_signups": 42}


def test_lead_count_endpoint_returns_current_count(monkeypatch) -> None:
    from backend.routers import leads

    class FakeLeadStore:
        def get_lead_count(self, lead_type: str) -> int:
            assert lead_type == "premium"
            return 42

    monkeypatch.setattr(leads, "lead_store", FakeLeadStore())

    response = client.get("/api/leads/count", params={"type": "premium"})

    assert response.status_code == 200
    assert response.json() == {"type": "premium", "count": 42}


def test_lead_count_endpoint_works_with_real_sqlite_store(tmp_path, monkeypatch) -> None:
    from backend.routers import leads

    store = LeadStore(tmp_path / "leads.db")
    store.save_lead("real@example.com", "premium")
    monkeypatch.setattr(leads, "lead_store", store)

    response = client.get("/api/leads/count", params={"type": "premium"})

    assert response.status_code == 200
    assert response.json() == {"type": "premium", "count": 1}
