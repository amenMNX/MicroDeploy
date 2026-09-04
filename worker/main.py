import os
import time

import psycopg2


# ── Exceptions ────────────────────────────────────────────────────────────────

class DatabaseUnavailableError(Exception):
    """Raised when the database cannot be reached after all retries."""


# ── Config ────────────────────────────────────────────────────────────────────

DB_PARAMS = {
    "host":     os.getenv("DB_HOST",     "db"),
    "database": os.getenv("DB_NAME",     "microdeploy"),
    "user":     os.getenv("DB_USER",     "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
}

# Fix #8 — catch the full set of psycopg2 errors on retry
_RETRYABLE = (psycopg2.OperationalError, psycopg2.DatabaseError, psycopg2.InterfaceError)

# Fix #6 — backoff settings
_IDLE_SLEEP   = 3.0    # seconds between polls when no tasks are pending
_ERROR_SLEEP  = 5.0    # seconds to wait after a processing error
_MAX_BACKOFF  = 60.0   # cap for idle backoff when queue stays empty


# ── DB startup check ──────────────────────────────────────────────────────────

def wait_for_db(retries: int = 10, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            conn.close()
            print("Worker connected to the database.")
            return
        except _RETRYABLE as exc:
            print(f"DB not ready (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(delay)
    raise DatabaseUnavailableError(f"Database unavailable after {retries} attempts")


# ── Task processing ───────────────────────────────────────────────────────────

def process_one() -> bool:
    """
    Claim and process one pending task.
    Returns True if a task was processed, False if the queue was empty.
    Raises on unexpected errors so the caller can back off.
    """
    conn = psycopg2.connect(**DB_PARAMS)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET status = 'done' "
            "WHERE id = (SELECT id FROM tasks WHERE status = 'pending' "
            "LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING id;"
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        if row:
            print(f"Worker processed task id: {row[0]}")
            return True
        return False
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()   # Fix #6 — always close; a pool would be better for high volume


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    wait_for_db()
    print("Worker is listening for tasks...")

    idle_sleep = _IDLE_SLEEP

    while True:
        try:
            did_work = process_one()

            if did_work:
                idle_sleep = _IDLE_SLEEP  # reset backoff after real work
            else:
                # Fix #6 — exponential backoff when queue is empty
                time.sleep(idle_sleep)
                idle_sleep = min(idle_sleep * 1.5, _MAX_BACKOFF)

        # Fix #7 — differentiate recoverable DB errors from unknown errors
        except _RETRYABLE as exc:
            print(f"DB error, will retry in {_ERROR_SLEEP}s: {exc}")
            time.sleep(_ERROR_SLEEP)
            idle_sleep = _IDLE_SLEEP   # reset so reconnect attempt isn't delayed further

        except Exception as exc:
            # Unknown error: log it clearly but keep the worker alive
            print(f"Unexpected error processing task: {type(exc).__name__}: {exc}")
            time.sleep(_ERROR_SLEEP)


if __name__ == "__main__":
    main()
