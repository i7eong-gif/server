from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import requests
from requests.exceptions import RequestException, Timeout

from app.core.cache import TTLCache


_CACHE = TTLCache(ttl_seconds=5)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REALTIME_TIMEOUT = (2, 3)

ET = ZoneInfo("America/New_York")


def is_us_regular_market(now: Optional[datetime] = None) -> bool:
    """ET 기준 장중 여부 (평일 09:30 ~ 16:00)"""
    now = now or datetime.now(ET)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return time(9, 30) <= t <= time(16, 0)


def _fetch_chart_meta(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(
            CHART_URL.format(symbol=symbol),
            params={"interval": "1m", "range": "1d"},
            timeout=REALTIME_TIMEOUT,
            headers={"User-Agent": "KRStockTray/1.0"},
        )
        r.raise_for_status()
        j = r.json()

        result = j.get("chart", {}).get("result")
        if not result:
            return None
        meta = result[0].get("meta")
        if not isinstance(meta, dict):
            return None
        return meta
    except (Timeout, RequestException, ValueError, KeyError, IndexError):
        return None


def get_us_realtime_quote(symbol: str) -> Optional[Dict[str, Any]]:
    symbol = (symbol or "").upper()
    cache_key = f"US_RT_QUOTE:{symbol}"

    cached = _CACHE.get(cache_key)
    if cached:
        cached = dict(cached)
        cached["cached"] = True
        return cached

    meta = _fetch_chart_meta(symbol)
    if not meta:
        return None

    price = meta.get("regularMarketPrice")
    prev = meta.get("previousClose")
    volume = meta.get("regularMarketVolume")

    if price is None or prev is None:
        return None

    data = {
        "price": float(price),
        "prev_close": float(prev),
        "volume": int(volume) if volume is not None else None,
        "cached": False,
    }

    _CACHE.set(cache_key, data)
    return data


if __name__ == "__main__":
    from pprint import pprint

    pprint(get_us_realtime_quote("QQQ"))
