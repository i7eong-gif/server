from app.providers.kr.kr_realtime import get_kr_realtime_price, is_kr_regular_market
from app.core.exceptions import StockNotFoundError


class KRProvider:
    def init_context(self, code: str) -> dict:
        realtime = get_kr_realtime_price(code)
        if not realtime:
            raise StockNotFoundError("KR", code)

        return {
            "market": "KR",
            "code": code,
            "realtime": realtime,
            "market_open": is_kr_regular_market(),
        }

    def get_quote(self, ctx: dict, plan: str) -> dict:
        realtime = ctx["realtime"]
        market_open = ctx["market_open"]

        price = realtime["price"]
        name = realtime.get("name")
        ref_price = realtime.get("prev_close") or 0
        volume = realtime.get("volume")
        price_type = "INTRADAY" if market_open else "AFTER_HOURS"

        delta = price - ref_price
        pct = round(delta / ref_price * 100, 2) if ref_price else 0.0

        data = {
            "market": "KR",
            "code": ctx["code"],
            "name": name,
            "price": price,
            "ref_price": ref_price,
            "delta": delta,
            "pct": pct,
            "price_type": price_type,
        }

        if plan != "free":
            data["volume"] = volume

        return data
