import os
import time

import psycopg2

DB_PARAMS = {
    "host": os.getenv("DB_HOST", "db"),
    "database": os.getenv("DB_NAME", "devops"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

def wait_for_db():
    for _ in range (10):
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            conn.close()
            print("Worker is connected to the db !!")
            return
        except psycopg2.OperationalError:
            time.sleep(2)
            
def main():
    wait_for_db()
    print("worker is listening for task !")
    while True : 
        try :
            conn =psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor()
            
            cur.execute("UPDATE tasks SET status = 'done' WHERE id = (SELECT id FROM tasks WHERE status = 'pending' LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING id;")
            res=cur.fetchone()
            
            if res:
                print(f"worker processed task id : {res[0]} ")
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:  # noqa: BLE001
            print(f"Error processing task: {e}")
        time.sleep(3)
if __name__ == "__main__":
    main()