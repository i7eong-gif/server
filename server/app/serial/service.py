"""Serial Service Layer

역할:
- Serial 발급(issue)
- Serial 해지(revoke)
- Serial 검증(validate) + 만료 자동 처리
- 최초 요청 시 디바이스 바인딩(bind)

주의:
- HTTP/FastAPI는 import하지 않는다 (순환 방지)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict

from app.serial.code import generate_serial, normalize_serial, is_valid_format
from app.serial import repository


TRIAL_DAYS_DEFAULT = 7


def issue_serial(plan: str, expire_days: Optional[int] = None) -> str:
    """새 시리얼 발급"""
    serial = generate_serial()
    issued_at = datetime.utcnow()
    expire_at = issued_at + timedelta(days=expire_days) if expire_days is not None else None

    repository.insert(
        serial=serial,
        plan=plan,
        issued_at=issued_at.isoformat(),
        expire_at=expire_at.isoformat() if expire_at else None,
    )
    return serial


def issue_or_get_trial_for_device(device_hash: str, expire_days: int = TRIAL_DAYS_DEFAULT) -> Dict:
    """디바이스 기준 체험판 시리얼을 1회 발급.

    - 같은 device_hash로 다시 요청하면 기존 활성 시리얼을 재사용한다.
      (재설치/설정 초기화 시에도 동일 PC는 계속 동일 라이선스를 사용)

    Returns:
        {"serial": str, "plan": str, "expire_at": Optional[str]}
    """
    device_hash = (device_hash or "").strip()
    if not device_hash:
        raise ValueError("DEVICE_REQUIRED")

    existing = repository.get_active_by_device(device_hash)
    if existing:
        serial, plan, _is_active, expire_at, _device, _activated_at = existing
        # 만료 되었으면 재발급 (체험판은 다시 발급하지 않는 정책도 가능하지만,
        # 여기서는 보수적으로 '만료된 active는 validate에서 비활성 처리'되므로
        # existing이 살아있다면 유효한 것으로 간주한다.)
        return {"serial": serial, "plan": plan, "expire_at": expire_at}

    serial = issue_serial(plan="trial", expire_days=expire_days)
    now = datetime.utcnow().isoformat()
    repository.bind_device(serial, device_hash, now)
    row = repository.get_by_serial(serial)
    expire_at = row[3] if row else None
    return {"serial": serial, "plan": "trial", "expire_at": expire_at}


def revoke_serial(serial: str) -> bool:
    serial = normalize_serial(serial)
    row = repository.get_by_serial(serial)
    if not row:
        return False
    repository.deactivate(serial, datetime.utcnow().isoformat())
    return True


def validate_serial(serial: str) -> Optional[Dict]:
    """시리얼 유효성 검증.

    Returns:
        {"plan": "free"} or None
    """
    serial = normalize_serial(serial)
    if not serial or not is_valid_format(serial):
        return None

    row = repository.get_by_serial(serial)

    if not row:
        return None

    _serial, plan, is_active, expire_at, _device_hash, _activated_at = row
    if not is_active:
        return None

    if expire_at:
        try:
            if datetime.utcnow() > datetime.fromisoformat(expire_at):
                repository.deactivate(serial, datetime.utcnow().isoformat())
                return None
        except Exception:
            # expire_at 파싱 실패 시 보수적으로 invalid 처리
            return None

    return {"plan": plan, "expire_at": expire_at}


def bind_or_verify_device(serial: str, device_hash: str) -> None:
    """디바이스 바인딩 처리.

    - device_hash는 클라이언트가 X-Device 헤더로 보낸 값.
    - 최초 사용 시(device_hash가 NULL) 자동 바인딩.
    - 이미 바인딩 되어있으면 동일 device_hash만 허용.

    Raises:
        ValueError("DEVICE_REQUIRED" | "DEVICE_MISMATCH" | "SERIAL_NOT_FOUND")
    """
    serial = normalize_serial(serial)
    device_hash = (device_hash or "").strip()
    if not device_hash:
        raise ValueError("DEVICE_REQUIRED")

    row = repository.get_by_serial(serial)
    if not row:
        raise ValueError("SERIAL_NOT_FOUND")

    _serial, _plan, _is_active, _expire_at, db_device, _activated_at = row
    now = datetime.utcnow().isoformat()

    if db_device is None:
        repository.bind_device(serial, device_hash, now)
        return

    if db_device != device_hash:
        raise ValueError("DEVICE_MISMATCH")

    # same device -> touch
    repository.touch(serial, now)

