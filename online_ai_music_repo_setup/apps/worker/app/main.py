import os
import time


def run_worker() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"AION worker started. Redis: {redis_url}", flush=True)

    while True:
        time.sleep(30)
        print("AION worker heartbeat", flush=True)


if __name__ == "__main__":
    run_worker()
