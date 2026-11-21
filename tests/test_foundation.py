import hashlib

from fastapi.testclient import TestClient

from meridian_agent.app import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_serves_original_generator() -> None:
    response = client.get("/web/vendor/challenge-generator.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert hashlib.sha256(response.content).hexdigest() == (
        "bd20df4c79e70da57b4d4ddf0215f642b4653ad1277c95cbac522fcc2f48a9f8"
    )


def test_missing_static_asset_returns_not_found() -> None:
    assert client.get("/web/unknown.html").status_code == 404
