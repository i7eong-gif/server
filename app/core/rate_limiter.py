# app/core/rate_limiter.py
import time
from collections import defaultdict, deque
from fastapi import HTTPException

# key -> timestamps
_request_log: dict[str, deque] = defaultdict(deque)

RATE_LIMITS = {
    "trial": {"window": 60, "max_requests": 20},
    "free": {"window": 60, "max_requests": 30},
    "pro": {"window": 60, "max_requests": 300},
    "enterprise": {"window": 60, "max_requests": 3000},
}


def check_rate_limit(identifier: str, plan: str):
    rule = RATE_LIMITS[plan]
    now = time.time()
    window = rule["window"]
    max_req = rule["max_requests"]

    q = _request_log[identifier]

    # 오래된 요청 제거
    while q and q[0] <= now - window:
        q.popleft()

    if len(q) >= max_req:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "window": window,
                "max_requests": max_req
            }
        )

    q.append(now)


if __name__ == "__main__":
    print("=== rate limiter test ===")

    key = "test_key"
    plan = "free"

    # free: 30 req / min
    for i in range(30):
        check_rate_limit(key, plan)

    try:
        check_rate_limit(key, plan)
        raise RuntimeError("Should have been rate limited")
    except Exception as e:
        print("[OK] rate limited")

    print("rate limiter OK")