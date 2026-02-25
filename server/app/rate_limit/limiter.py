"""
Rate Limit 핵심 로직 파일

- API Key + plan 기준으로 요청 수를 제한한다.
- In-memory 방식 (프로세스 단위)
- Token Bucket이 아닌 Fixed Window (단순/안정)

주의:
- Fly.io scale-out 시 Redis로 교체 필요
"""

import time
from collections import defaultdict, deque
from threading import Lock

# plan별 정책 (req / window)
PLAN_LIMITS = {
    "free": 60,
    "pro": 600,
    "enterprise": 6000,
}

WINDOW_SECONDS = 60


class RateLimiter:
    """
    key별 요청 시간을 deque로 관리한다.
    """
    def __init__(self):
        self._buckets = defaultdict(deque)
        self._lock = Lock()

    def allow(self, api_key: str, plan: str) -> bool:
        """
        요청을 허용할지 판단한다.

        return:
            True  -> 허용
            False -> rate limit 초과
        """
        limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        now = time.time()

        with self._lock:
            q = self._buckets[api_key]

            # window 밖의 요청 제거
            while q and now - q[0] > WINDOW_SECONDS:
                q.popleft()

            if len(q) >= limit:
                return False

            q.append(now)
            return True


# 싱글톤
rate_limiter = RateLimiter()


# ------------------------------
# 간이 테스트
# ------------------------------
if __name__ == "__main__":
    rl = RateLimiter()
    key = "test-key"

    # free plan 60회 허용
    for i in range(60):
        assert rl.allow(key, "free") is True

    # 61번째는 거부
    assert rl.allow(key, "free") is False

    print("RateLimiter self-test OK")
