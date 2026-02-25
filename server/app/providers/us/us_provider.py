from app.core.exceptions import StockNotFoundError
from app.providers.us.us_realtime import get_us_realtime_quote, is_us_regular_market


class USProvider:
    def init_context(self, code: str) -> dict:
        code = (code or "").upper()
        realtime = get_us_realtime_quote(code)
        if not realtime:
            raise StockNotFoundError("US", code)

        return {
            "market": "US",
            "code": code,
            "realtime": realtime,
            "market_open": is_us_regular_market(),
        }

    def get_quote(self, ctx: dict, plan: str) -> dict:
        realtime = ctx["realtime"]
        market_open = ctx["market_open"]

        price = realtime["price"]
        ref_price = realtime["prev_close"]
        delta = price - ref_price
        pct = round(delta / ref_price * 100, 2) if ref_price else 0.0
        price_type = "INTRADAY" if market_open else "AFTER_HOURS"

        data = {
            "market": "US",
            "code": ctx["code"],
            "price": price,
            "ref_price": ref_price,
            "delta": delta,
            "pct": pct,
            "price_type": price_type,
        }

        if plan != "free":
            vol = realtime.get("volume")
            if vol is not None:
                data["volume"] = int(vol)

        return data
