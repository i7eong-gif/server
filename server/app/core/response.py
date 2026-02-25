# app/core/response.py
from fastapi.responses import JSONResponse


def success(data: dict, ad: dict | None = None, notice: dict | None = None):
    """표준 성공 응답.

    - 기존: {"ok": true, "data": {...}, "ad"?: {...}}
    - 추가: notice (만료 임박 안내 등)

    클라이언트에서 notice를 무시해도 기존 동작은 유지된다.
    """

    resp = {"ok": True, "data": data}
    if ad:
        resp["ad"] = ad
    if notice:
        resp["notice"] = notice
    return resp

def error_response(code: str, message: str, status_code: int):
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": {
                "code": code,
                "message": message
            }
        }
    )