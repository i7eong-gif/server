"""
Admin Routers

Admin 전용 API:
- API Key 발급
- API Key 해지
- API Key 목록 조회

설계 원칙:
- Admin 인증은 require_admin dependency로만 처리
- 비즈니스 로직은 auth/service.py에 위임
- SQLite 단일 저장소를 단일 진실 소스로 사용
- prefix는 main.py에서만 부여 (/admin)
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Tuple

from app.admin.security import require_admin

# ✅ Serial(License) 관리
from app.serial.service import issue_serial, revoke_serial
from app.serial.repository import list_serials, update_serial, reset_device_binding, get_by_serial
from app.core.response import success

router = APIRouter(prefix="/admin", tags=["admin"])
# ⚠️ prefix는 여기서만 설정. main.py의 include_router에는 prefix 없음.


# =========================================================
# Request / Response Models
# =========================================================

class IssueSerialRequest(BaseModel):
    """시리얼 발급 요청"""
    plan: str
    expire_days: Optional[int] = None


class SerialItem(BaseModel):
    serial: str
    plan: str
    is_active: int
    issued_at: str
    expire_at: Optional[str]
    revoked_at: Optional[str]
    device_hash: Optional[str]
    activated_at: Optional[str]
    last_seen_at: Optional[str]


class UpdateSerialRequest(BaseModel):
    plan: Optional[str] = None
    expire_days: Optional[int] = None



# =========================================================
# Serial (License) Routes
# =========================================================


@router.post("/serials")
def create_serial(
    body: IssueSerialRequest,
    _: None = Depends(require_admin),
):
    """시리얼 발급 (Admin Only)

    POST /admin/serials
    Body:
        {
          "plan": "free" | "pro" | "enterprise",
          "expire_days": 1 | null
        }
    """
    serial = issue_serial(plan=body.plan, expire_days=body.expire_days)
    return success({"serial": serial, "plan": body.plan})


@router.delete("/serials/{serial}")
def delete_serial(
    serial: str,
    _: None = Depends(require_admin),
):
    """시리얼 해지 (Admin Only)"""
    revoked = revoke_serial(serial)
    return success({"serial": serial, "revoked": revoked})


@router.get("/serials")
def get_serials(
    _: None = Depends(require_admin),
):
    """시리얼 목록 조회 (Admin Only)"""
    rows: List[Tuple] = list_serials()
    data = [
        {
            "serial": r[0],
            "plan": r[1],
            "is_active": r[2],
            "issued_at": r[3],
            "expire_at": r[4],
            "revoked_at": r[5],
            "device_hash": r[6],
            "activated_at": r[7],
            "last_seen_at": r[8],
        }
        for r in rows
    ]
    return success(data)


@router.patch("/serials/{serial}")
def update_serial_route(
    serial: str,
    body: UpdateSerialRequest,
    _=Depends(require_admin),
):
    serial_row = get_by_serial(serial)
    if not serial_row:
        raise HTTPException(status_code=404, detail="Serial not found")

    fields: dict = {}

    if body.plan is not None:
        fields["plan"] = body.plan

    if body.expire_days is not None:
        fields["expire_at"] = (
            datetime.utcnow() + timedelta(days=body.expire_days)
        ).isoformat()
        fields["is_active"] = 1
        fields["revoked_at"] = None

    if not fields:
        return success({"serial": serial, "updated": False})

    update_serial(serial=serial, **fields)
    return success({"serial": serial, "updated": True})


@router.post("/serials/{serial}/reset-device")
def reset_serial_device(
    serial: str,
    _: None = Depends(require_admin),
):
    """디바이스 바인딩 초기화 (Admin Only)

    - 사용자가 PC를 교체했을 때 등을 위해 제공
    """
    reset_device_binding(serial)
    return success({"serial": serial, "reset": True})


