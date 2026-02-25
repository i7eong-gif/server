"""code.py

시리얼(라이선스 번호) 문자열 생성/검증 유틸.

목표:
- 사람이 입력/전달하기 쉬운 형태
- 서버 DB에서만 의미를 갖도록 (개인정보/기기정보를 시리얼 자체에 넣지 않음)
- 간단한 오타 검출(checksum) 지원

형식:
    KRST-XXXX-XXXX-XXXX-C

  - X : base32 문자(0-9,A-V) 중 일부
  - C : 체크섬 1글자 (오타 검출용)
"""

from __future__ import annotations

import secrets
import string


_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # 혼동 문자(I, L, O, U) 제거


def _rand_group(n: int = 4) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _checksum(body: str) -> str:
    """매우 가벼운 체크섬.

    - 암호학적 목적이 아니라 오타 검출용
    - body는 하이픈 없이/대문자 기준
    """
    s = 0
    for ch in body:
        s = (s * 33 + ord(ch)) % 31
    return _ALPHABET[s]


def generate_serial(prefix: str = "KRST") -> str:
    """새 시리얼 발급."""
    g1, g2, g3 = _rand_group(), _rand_group(), _rand_group()
    body = f"{prefix}{g1}{g2}{g3}".upper()
    c = _checksum(body)
    return f"{prefix}-{g1}-{g2}-{g3}-{c}".upper()


def normalize_serial(s: str) -> str:
    return (s or "").strip().upper()


def is_valid_format(s: str) -> bool:
    s = normalize_serial(s)
    parts = s.split("-")
    if len(parts) != 5:
        return False
    prefix, g1, g2, g3, c = parts
    if prefix != "KRST":
        return False
    if not all(len(g) == 4 for g in (g1, g2, g3)):
        return False
    if len(c) != 1:
        return False
    allowed = set(_ALPHABET)
    if any(ch not in allowed for ch in (g1 + g2 + g3 + c)):
        return False
    body = f"{prefix}{g1}{g2}{g3}".upper()
    return _checksum(body) == c


if __name__ == "__main__":
    # 단독 테스트
    s = generate_serial()
    print("serial:", s)
    assert is_valid_format(s)
    assert not is_valid_format(s[:-1] + "Z")
    print("[OK] serial code")
