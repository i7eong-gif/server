# app/rate_limit/dependencies.py
from fastapi import HTTPException, Request
import time
from app.policies.rate_limit import RATE_LIMITS

# in-memory token bucket (API Key 단위)
_BUCKET: dict[str, list[float]] = {}


def rate_limit_dependency(request: Request, api_ctx: dict):
    """
    request, api_ctx를 명시적으로 받아 호출하는 rate limit
    """
    api_key = api_ctx["api_key"]
    plan = api_ctx["plan"]["name"]

    policy = RATE_LIMITS.get(plan, RATE_LIMITS["free"])
    window = policy["window"]
    limit = policy["max_requests"]

    now = time.time()
    bucket = _BUCKET.setdefault(api_key, [])

    # window 밖 요청 제거
    bucket[:] = [t for t in bucket if now - t < window]

    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="RATE_LIMIT_EXCEEDED")

    bucket.append(now)

