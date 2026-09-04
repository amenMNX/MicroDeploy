import os
import time

import psycopg2

DB_PARAMS = {
    "host": os.getenv("DB_HOST", "db"),
    "database": os.getenv("DB_NAME", "microdeploy"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
}


class DatabaseUnavailableError(Exception):
    """Raised when the database cannot be reached after retries."""


def wait_for_db():
    for _ in range(10):
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            conn.close()
            print("Worker connected to the database.")
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise DatabaseUnavailableError("Database not available after retries")


def main():
    wait_for_db()
    print("Worker is listening for tasks...")
    while True:
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor()

            cur.execute(
                "UPDATE tasks SET status = 'done' "
                "WHERE id = (SELECT id FROM tasks WHERE status = 'pending' "
                "LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING id;"
            )
            res = cur.fetchone()

            if res:
                print(f"Worker processed task id: {res[0]}")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:  # noqa: BLE001
            print(f"Error processing task: {e}")
        time.sleep(3)


if __name__ == "__main__":
    main()
