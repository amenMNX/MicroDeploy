import os
import time
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel


class DatabaseUnavailableError(Exception):
    """Raised when the database cannot be reached after retries."""


DB_PARAMS = {
    "host": os.getenv("DB_HOST", "db"),
    "database": os.getenv("DB_NAME", "microdeploy"), 
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
}


def wait_for_db():
    for _ in range(10):
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise DatabaseUnavailableError("Database not available")

@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    yield

app = FastAPI(title="Main DevOps API", lifespan=lifespan)

class Task(BaseModel):
    title: str

@app.get("/")
def root():
    return {"status": "running", "service": "api"}

@app.post("/tasks")
def create_task(task: Task):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title) VALUES (%s) RETURNING id;", (task.title,))
    task_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"id": task_id, "title": task.title, "status": "pending"}

@app.get("/tasks")
def get_tasks():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT id, title, status FROM tasks;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "title": r[1], "status": r[2]} for r in rows]

@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}