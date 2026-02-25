from __future__ import annotations

from fastapi import Header, HTTPException, status
from datetime import datetime, timezone

from app.serial.service import validate_serial, bind_or_verify_device


def get_api_context_from_serial(
    x_serial: str | None = Header(None, alias="X-Serial"),
    x_device: str | None = Header(None, alias="X-Device"),
):
    if not x_serial:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Serial header",
        )

    info = validate_serial(x_serial)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired serial",
        )

    plan_name = info["plan"]

    # trial은 디바이스 바인딩 필수, 나머지는 X-Device 있을 때만 적용
    if plan_name == "trial" or x_device:
        try:
            bind_or_verify_device(x_serial, x_device or "")
        except ValueError as e:
            code = str(e)
            if code == "DEVICE_REQUIRED":
                raise HTTPException(status_code=401, detail="Missing X-Device header")
            if code == "DEVICE_MISMATCH":
                raise HTTPException(status_code=403, detail="Serial bound to another device")
            raise HTTPException(status_code=401, detail="Invalid serial")

    # days_left 계산(만료 없으면 None)
    days_left = None
    expire_at = info.get("expire_at") if isinstance(info, dict) else None
    if expire_at:
        try:
            dt = datetime.fromisoformat(str(expire_at))
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            days_left = (dt - now_utc).days
        except Exception:
            days_left = None

    return {
        # ✅ 기존 rate_limit이 api_key를 키로 쓰고 있어 호환을 위해 유지
        "api_key": (x_serial or "").strip().upper(),
        "plan": {"name": info["plan"], "expire_at": expire_at, "days_left": days_left},
    }

