from fastapi import APIRouter
from app.symbols.krx_provider import PROVIDER

router = APIRouter()

@router.get("/symbols/KR/all")
def get_all_kr_symbols():
    items = PROVIDER.get_all()

    return {
        "ok": True,
        "updated_at": PROVIDER.updated_at(),
        "data": [
            {
                "code": s.code,
                "name": s.name,
                "market": s.market,  # KRX / ETF
            }
            for s in items
        ],
    }
