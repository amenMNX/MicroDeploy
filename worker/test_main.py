from unittest.mock import MagicMock, call, patch

import psycopg2
import pytest

import main
from main import DatabaseUnavailableError, process_one, wait_for_db


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_conn(fetchone_val=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_val
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


# ── Smoke tests ───────────────────────────────────────────────────────────────

def test_worker_main_is_callable():
    assert callable(main.main)


def test_worker_wait_for_db_is_callable():
    assert callable(main.wait_for_db)


def test_db_params_database():
    assert main.DB_PARAMS["database"] == "microdeploy"


def test_db_params_default_host():
    assert main.DB_PARAMS["host"] == "db"


def test_database_unavailable_error_exists():
    assert issubclass(DatabaseUnavailableError, Exception)


# ── wait_for_db ───────────────────────────────────────────────────────────────

def test_wait_for_db_succeeds_on_first_try():
    with patch("main.psycopg2.connect") as mock_connect:
        mock_connect.return_value = MagicMock()
        wait_for_db(retries=3, delay=0)
    mock_connect.assert_called_once()


def test_wait_for_db_retries_then_succeeds():
    conn = MagicMock()
    with patch("main.psycopg2.connect", side_effect=[psycopg2.OperationalError, conn]) as mock_connect:
        wait_for_db(retries=3, delay=0)
    assert mock_connect.call_count == 2


def test_wait_for_db_raises_after_all_retries():
    with patch("main.psycopg2.connect", side_effect=psycopg2.OperationalError):
        with pytest.raises(DatabaseUnavailableError):
            wait_for_db(retries=3, delay=0)


def test_wait_for_db_retries_on_database_error():
    """Fix #8 – should retry on DatabaseError too, not just OperationalError."""
    conn = MagicMock()
    with patch("main.psycopg2.connect", side_effect=[psycopg2.DatabaseError, conn]):
        wait_for_db(retries=3, delay=0)  # should not raise


# ── process_one ───────────────────────────────────────────────────────────────

def test_process_one_returns_true_when_task_found():
    conn, cur = _make_conn(fetchone_val=(7,))
    with patch("main.psycopg2.connect", return_value=conn):
        result = process_one()
    assert result is True
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_process_one_returns_false_when_queue_empty():
    conn, cur = _make_conn(fetchone_val=None)
    with patch("main.psycopg2.connect", return_value=conn):
        result = process_one()
    assert result is False
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_process_one_rolls_back_on_error():
    conn = MagicMock()
    conn.cursor.side_effect = psycopg2.OperationalError("boom")
    with patch("main.psycopg2.connect", return_value=conn):
        with pytest.raises(psycopg2.OperationalError):
            process_one()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_process_one_closes_connection_even_on_error():
    """Fix #6/#7 – connection must be returned even when processing fails."""
    conn = MagicMock()
    conn.cursor.side_effect = RuntimeError("unexpected")
    with patch("main.psycopg2.connect", return_value=conn):
        with pytest.raises(RuntimeError):
            process_one()
    conn.close.assert_called_once()
