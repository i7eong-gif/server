from fastapi import APIRouter, Request, Header

from app.serial.dependencies import get_api_context_from_serial
from app.rate_limit.dependencies import rate_limit_dependency
from app.providers.factory import get_provider
from app.core.cache import TTLCache
from app.core.exceptions import StockNotFoundError
from app.core.response import success

router = APIRouter(prefix="/quote", tags=["quote"])

_quote_cache = TTLCache(ttl_seconds=3)


@router.get("/{market}/{code}")
def quote(
    market: str,
    code: str,
    request: Request,
    x_serial: str | None = Header(None, alias="X-Serial"),
    x_device: str | None = Header(None, alias="X-Device"),
):
    api_ctx = get_api_context_from_serial(x_serial=x_serial, x_device=x_device)
    rate_limit_dependency(request, api_ctx)

    plan = api_ctx["plan"]["name"]
    key = f"{market.upper()}:{code.upper()}"

    cached = _quote_cache.get(key)
    if cached:
        out = dict(cached)
        out["cached"] = True
        return success(out, notice=_build_notice(api_ctx))

    provider = get_provider(market)

    try:
        ctx = provider.init_context(code)
        data = provider.get_quote(ctx, plan=plan)
        _quote_cache.set(key, data)
    except StockNotFoundError:
        raise
    except Exception:
        stale = _quote_cache.get(key)
        if stale:
            return success(dict(stale) | {"status": "stale"}, notice=_build_notice(api_ctx))
        raise

    return success(data, notice=_build_notice(api_ctx))


def _build_notice(api_ctx: dict) -> dict | None:
    try:
        plan = (api_ctx.get("plan") or {}).get("name")
        days_left = (api_ctx.get("plan") or {}).get("days_left")
        if str(plan) == "trial" and isinstance(days_left, int) and days_left <= 3:
            return {"type": "trial_expiring", "days_left": days_left}
    except Exception:
        pass
    return None
