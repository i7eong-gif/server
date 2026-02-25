"""activate.py

체험판(Trial) 자동 발급 API.

클라이언트(KRStockTray)에서 시리얼이 없을 때 1회 호출해서
디바이스에 바인딩된 trial 시리얼을 발급/재사용한다.

요구 헤더:
  - X-Device: 클라이언트 디바이스 해시

응답:
  {"ok": true, "data": {"serial": "...", "plan": "trial", "expire_at": "..."}}
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.serial.service import issue_or_get_trial_for_device
from app.core.response import success


router = APIRouter(prefix="/activate", tags=["activate"])


@router.post("/trial")
def activate_trial(
    x_device: str | None = Header(None, alias="X-Device"),
):
    """디바이스 기준 trial 시리얼 발급/재사용."""
    try:
        info = issue_or_get_trial_for_device(x_device or "")
    except ValueError as e:
        if str(e) == "DEVICE_REQUIRED":
            raise HTTPException(status_code=401, detail="Missing X-Device header")
        raise HTTPException(status_code=400, detail="Invalid device")

    return success({
        "serial": info["serial"],
        "plan": info.get("plan", "trial"),
        "expire_at": info.get("expire_at"),
    })


if __name__ == "__main__":
    # standalone smoke test
    from app.core.db import init_db

    init_db()
    print(activate_trial(x_device="devhash"))
