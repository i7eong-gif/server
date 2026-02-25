import requests
from bs4 import BeautifulSoup
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional
from app.core.cache import TTLCache

_CACHE = TTLCache(ttl_seconds=5)

KST = ZoneInfo("Asia/Seoul")
BASE_URL = "https://finance.naver.com/item/sise.naver"

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
})


def is_kr_regular_market(now: Optional[datetime] = None) -> bool:
    """KST 기준 장중 여부 (평일 09:00 ~ 15:30)"""
    now = now or datetime.now(KST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return time(9, 0) <= t <= time(15, 30)


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(
            str(v)
            .replace(",", "")
            .replace("+", "")
            .replace("▲", "")
            .replace("▼", "")
            .strip()
        )
    except Exception:
        return None


def _extract_name(soup) -> Optional[str]:
    """dl.blind 에서 종목명 추출"""
    dl = soup.select_one("dl.blind")
    if not dl:
        return None
    for dd in dl.select("dd"):
        text = dd.get_text(strip=True)
        if text.startswith("종목명 "):
            return text[4:].strip()
    return None


def _extract_price(block) -> Optional[int]:
    if not block:
        return None
    tag = block.select_one(".today .no_today .blind")
    return _to_int(tag.get_text()) if tag else None


def _extract_prev_close(block) -> Optional[int]:
    """전일종가 추출 (항상 KRX 블록에서)"""
    if not block:
        return None
    for td in block.select("table.no_info td"):
        label = td.select_one("span.sptxt.sp_txt2")
        if label:
            tag = td.select_one(".blind")
            if tag:
                return _to_int(tag.get_text())
    return None


def _extract_volume(block) -> int:
    if not block:
        return 0
    for td in block.select("table.no_info td"):
        label = td.select_one("span.sptxt.sp_txt9")
        if label:
            tag = td.select_one(".blind")
            if tag:
                return _to_int(tag.get_text()) or 0
    return 0


def get_kr_realtime_price(code: str) -> dict | None:
    cache_key = f"KR_REALTIME:{code}"
    cached = _CACHE.get(cache_key)
    if cached is not None:
        out = dict(cached)
        out["cached"] = True
        return out

    try:
        r = _session.get(BASE_URL, params={"code": code}, timeout=3)
        r.raise_for_status()
        r.encoding = r.apparent_encoding

        soup = BeautifulSoup(r.text, "html.parser")
        krx_block = soup.select_one("#rate_info_krx")
        nxt_block = soup.select_one("#rate_info_nxt")

        if not krx_block:
            return None

        # 가격: 장중 → KRX, 시간외 → NXT 우선 → KRX 폴백
        if is_kr_regular_market():
            price = _extract_price(krx_block)
        else:
            nxt_price = _extract_price(nxt_block)
            price = nxt_price if nxt_price else _extract_price(krx_block)

        if price is None:
            return None

        name = _extract_name(soup)
        prev_close = _extract_prev_close(krx_block)
        total_volume = _extract_volume(krx_block) + _extract_volume(nxt_block)

        data = {
            "name": name,
            "price": price,
            "prev_close": prev_close,
            "volume": total_volume if total_volume > 0 else None,
            "cached": False,
        }
        _CACHE.set(cache_key, data)
        return data

    except Exception:
        return None


if __name__ == "__main__":
    from pprint import pprint
    print("=== KR realtime test (same process) ===")
    pprint(get_kr_realtime_price("005930"))
    pprint(get_kr_realtime_price("005930"))
