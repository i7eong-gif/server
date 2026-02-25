# tickers/loader.py
import json
import os
from datetime import datetime

# =====================================================
# KR 종목 리스트 (kr.json)
# =====================================================
_PATH = os.path.join(os.path.dirname(__file__), "kr.json")
_CACHE = None
_KR_BY_CODE = None

def load():
    global _CACHE
    if _CACHE is None:
        with open(_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE

def search_kr(keyword: str, limit=50):
    keyword = keyword.strip()
    if not keyword:
        return []
    out = []
    for row in load():
        if keyword in row["name"]:
            out.append((row["name"], row["code"]))
            if len(out) >= limit:
                break
    return out

def load_kr_by_code():
    global _KR_BY_CODE
    if _KR_BY_CODE is not None:
        return _KR_BY_CODE

    rows = load()
    _KR_BY_CODE = {row["code"]: row["name"] for row in rows}
    return _KR_BY_CODE


def get_kr_name(code: str) -> str:
    """
    KR 종목 코드 → 종목명
    없으면 code 그대로 반환
    """
    m = load_kr_by_code()
    return m.get(code, code)

# =====================================================
# KRX 휴장일 로더 (krx_holidays.json)
# =====================================================
_KRX_HOLIDAYS_CACHE = None

def load_krx_holidays(path: str) -> set[str]:
    """
    krx_holidays.json 로드
    return: {"2025-01-01", ...}
    """
    global _KRX_HOLIDAYS_CACHE

    if _KRX_HOLIDAYS_CACHE is not None:
        return _KRX_HOLIDAYS_CACHE

    if not os.path.exists(path):
        _KRX_HOLIDAYS_CACHE = set()
        return _KRX_HOLIDAYS_CACHE

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        year = str(datetime.now().year)
        days = data.get(year, [])
        _KRX_HOLIDAYS_CACHE = set(days)

    except Exception:
        _KRX_HOLIDAYS_CACHE = set()

    return _KRX_HOLIDAYS_CACHE