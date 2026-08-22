from unittest.mock import patch
from fastapi.testclient import TestClient

# Patch wait_for_db before importing app so lifespan doesn't try to connect
with patch("main.wait_for_db"):
    from main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}