from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Patch wait_for_db before importing app so import/lifespan DB wait doesn't run.
with patch("main.wait_for_db"):
    from main import app


@pytest.fixture
def client():
    # TestClient construction triggers the app lifespan, so patch both startup DB helpers.
    with patch("main.wait_for_db"), patch("main.get_pool"):
        with TestClient(app) as test_client:
            yield test_client


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def _make_mock_conn(fetchone_val=None, fetchall_val=None):
    """Return a mock psycopg2 connection wired up for common cursor operations."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_val
    mock_cur.fetchall.return_value = fetchall_val or []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn


def test_create_task(client):
    mock_conn = _make_mock_conn(fetchone_val=(42,))
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch("main.get_pool", return_value=mock_pool):
        response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    mock_pool.putconn.assert_called_once_with(mock_conn)


def test_get_tasks(client):
    mock_conn = _make_mock_conn(
        fetchall_val=[(1, "Task A", "pending"), (2, "Task B", "done")]
    )
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch("main.get_pool", return_value=mock_pool):
        response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert tasks[0] == {"id": 1, "title": "Task A", "status": "pending"}
    assert tasks[1] == {"id": 2, "title": "Task B", "status": "done"}
    mock_pool.putconn.assert_called_once_with(mock_conn)


def test_get_tasks_empty(client):
    mock_conn = _make_mock_conn(fetchall_val=[])
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch("main.get_pool", return_value=mock_pool):
        response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == []
    mock_pool.putconn.assert_called_once_with(mock_conn)