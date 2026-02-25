from typing import List
from fastapi import APIRouter, Depends, Header, Request

from app.serial.dependencies import get_api_context_from_serial
from app.rate_limit.dependencies import rate_limit_dependency
from app.providers.factory import get_provider
from app.core.cache import TTLCache
from app.core.exceptions import StockNotFoundError
from app.core.response import success
from pydantic import BaseModel

router = APIRouter(prefix="/tray", tags=["tray"])

class TrayItem(BaseModel):
    market: str
    code: str


# tray 전용 캐시
_tray_cache = TTLCache(ttl_seconds=3)


@router.post("/quotes")
async def tray_quotes(
    items: List[TrayItem],
    request: Request,
    x_serial: str | None = Header(None, alias="X-Serial"),
    x_device: str | None = Header(None, alias="X-Device"),
):
    api_ctx = get_api_context_from_serial(
        x_serial=x_serial,
        x_device=x_device,
    )

    # rate limit (명시 호출)
    rate_limit_dependency(request, api_ctx)

    plan_info = api_ctx["plan"]
    plan = plan_info["name"]

    # trial 만료 임박 notice (quote와 동일 기준)
    notice = None
    days_left = plan_info.get("days_left")
    if plan == "trial" and isinstance(days_left, int) and days_left <= 3:
        notice = {"type": "trial_expiring", "days_left": days_left}

    result: dict = {}

    for item in items:
        key = f"{item.market}:{item.code}"

        cached = _tray_cache.get(key)
        if cached:
            out = dict(cached)
            out["cached"] = True
            result[key] = out
            continue

        provider = get_provider(item.market)

        try:
            ctx = provider.init_context(item.code)
            quote = provider.get_quote(ctx, plan=plan)

            _tray_cache.set(key, quote)
            result[key] = quote

        except StockNotFoundError:
            result[key] = {"status": "not_found"}
        except Exception:
            stale = _tray_cache.get(key)
            if stale:
                result[key] = dict(stale) | {"status": "stale"}
            else:
                result[key] = {"status": "error"}

    return success(result, notice=notice)
