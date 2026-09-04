import os
import time
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.pool
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel


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

# Fix #5 — connection pool instead of a new connection per request.
# min/max sizes are conservative; tune for your workload.
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, **DB_PARAMS)
    return _pool


# ── DB startup check ──────────────────────────────────────────────────────────

# Fix #8 — catch the full set of psycopg2 errors, not just OperationalError.
_RETRYABLE = (psycopg2.OperationalError, psycopg2.DatabaseError, psycopg2.InterfaceError)


def wait_for_db(retries: int = 10, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            conn.close()
            return
        except _RETRYABLE as exc:
            print(f"DB not ready (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(delay)
    raise DatabaseUnavailableError(f"Database unavailable after {retries} attempts")


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    get_pool()          # warm up the pool on startup
    yield
    if _pool and not _pool.closed:
        _pool.closeall()


app = FastAPI(title="MicroDeploy API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "MicroDeploy API", "status": "running"}


class Task(BaseModel):
    title: str


@app.post("/tasks")
def create_task(task: Task):
    pool = get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tasks (title) VALUES (%s) RETURNING id;",
            (task.title,),
        )
        task_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return {"id": task_id, "title": task.title, "status": "pending"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to create task") from exc
    finally:
        pool.putconn(conn)   # always return the connection to the pool


@app.get("/tasks")
def get_tasks():
    pool = get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, status FROM tasks;")
        rows = cur.fetchall()
        cur.close()
        return [{"id": r[0], "title": r[1], "status": r[2]} for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch tasks") from exc
    finally:
        pool.putconn(conn)


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}
