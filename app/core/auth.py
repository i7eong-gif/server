"""app/core/auth.py

✅ 목적
  - Authorization 헤더에서 Bearer 토큰(API Key)을 꺼내는 작은 유틸/Depends.

왜 core에 있나?
  - '토큰 문자열 파싱'은 auth(DB/정책)와 분리된, 순수한 파싱 로직이다.
  - 테스트(app/tests/test_auth.py)에서 이 함수를 직접 검증한다.

규칙
  - Authorization 형식: "Bearer <api_key>"
  - 그 외 형식은 None
"""

from __future__ import annotations

from fastapi import Header


def get_api_key(authorization: str | None = Header(None)) -> str | None:
    """Authorization 헤더에서 API Key 문자열만 추출한다.

    - 없으면 None
    - 'Bearer '로 시작하지 않으면 None
    - 빈 문자열이면 None
    """

    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    key = authorization.removeprefix("Bearer ").strip()
    return key or None


if __name__ == "__main__":
    print("=== core.auth self-test ===")
    assert get_api_key(None) is None
    assert get_api_key("abc") is None
    assert get_api_key("Bearer  ") is None
    assert get_api_key("Bearer sk_live_demo") == "sk_live_demo"
    print("[OK] core.auth")
