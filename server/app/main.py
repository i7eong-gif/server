"""app/main.py

✅ 메인 FastAPI 엔트리포인트

중요: DB 초기화
  - SQLite 기반 API Key/플랜 단일화를 위해,
    앱이 시작될 때 app/auth/init_db.py의 init_db()를 반드시 호출한다.
  - 이렇게 하면 새 환경에서도 'no such table/column' 류의 문제가 크게 줄어든다.
"""

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.core.response import success, error_response
from app.core.exceptions import StockNotFoundError, InvalidMarketError
from app.routers import tray
from app.routers.activate import router as activate_router
from app.core.db import init_db
from app.admin.routers import router as admin_router
from app.routers.quote import router as quote_router
from app.symbols.router import router as symbols_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -----------------
    # startup
    # -----------------
    init_db()

    yield

    # -----------------
    # shutdown
    # -----------------
    # (지금은 정리할 리소스 없음)


app = FastAPI(title="Stock API", lifespan=lifespan)

# -----------------
# routers
# -----------------
app.include_router(tray.router)
app.include_router(quote_router)
app.include_router(activate_router)
app.include_router(admin_router)
app.include_router(symbols_router)

@app.get("/health")
def health():
    return success({"status": "ok"})

@app.exception_handler(StockNotFoundError)
async def stock_not_found_handler(request: Request, exc: StockNotFoundError):
    return error_response(
        code=f"{exc.market}_NOT_FOUND",
        message=f"stock code not found: {exc.code}",
        status_code=404
    )

@app.exception_handler(InvalidMarketError)
async def invalid_market_handler(request, exc: InvalidMarketError):
    return error_response(
        code="INVALID_MARKET",
        message=f"invalid market: {exc.market}",
        status_code=400
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return error_response(
        code="INTERNAL_ERROR",
        message=str(exc),
        status_code=500
    )
