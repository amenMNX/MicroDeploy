from unittest.mock import MagicMock, patch

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


def _make_mock_conn(fetchone_val=None, fetchall_val=None):
    """Return a mock psycopg2 connection wired up for common cursor operations."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone_val
    mock_cur.fetchall.return_value = fetchall_val or []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn


def test_create_task():
    mock_conn = _make_mock_conn(fetchone_val=(42,))
    with patch("main.psycopg2.connect", return_value=mock_conn):
        response = client.post("/tasks", json={"title": "Write tests"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"


def test_get_tasks():
    mock_conn = _make_mock_conn(
        fetchall_val=[(1, "Task A", "pending"), (2, "Task B", "done")]
    )
    with patch("main.psycopg2.connect", return_value=mock_conn):
        response = client.get("/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert tasks[0] == {"id": 1, "title": "Task A", "status": "pending"}
    assert tasks[1] == {"id": 2, "title": "Task B", "status": "done"}


def test_get_tasks_empty():
    mock_conn = _make_mock_conn(fetchall_val=[])
    with patch("main.psycopg2.connect", return_value=mock_conn):
        response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []
