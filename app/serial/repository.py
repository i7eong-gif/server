"""Serial Repository (SQLite)

역할:
- serials 테이블 CRUD
- 비즈니스 로직 없음 (만료 판단/바인딩 판단 금지)

스키마:
  serials (
    serial TEXT PRIMARY KEY,
    plan TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    issued_at TEXT NOT NULL,
    expire_at TEXT,
    revoked_at TEXT,
    device_hash TEXT,
    activated_at TEXT,
    last_seen_at TEXT
  )
"""

from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple
from datetime import datetime
from app.policies.plans import VALID_PLANS
from app.core.config import get_db_path
from app.serial.code import normalize_serial


def _get_conn():
    return sqlite3.connect(get_db_path(), check_same_thread=False)


def insert(
    serial: str,
    plan: str,
    issued_at: str,
    expire_at: Optional[str],
):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO serials
              (serial, plan, is_active, issued_at, expire_at, revoked_at, device_hash, activated_at, last_seen_at)
            VALUES
              (?, ?, 1, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (serial, plan, issued_at, expire_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_by_serial(serial: str) -> Optional[Tuple]:
    """(serial, plan, is_active, expire_at, device_hash, activated_at)"""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT serial, plan, is_active, expire_at, device_hash, activated_at
            FROM serials
            WHERE serial = ?
            """,
            (serial,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_active_by_device(device_hash: str) -> Optional[Tuple]:
    """해당 디바이스에 바인딩된 활성 시리얼 1개를 반환.

    Returns:
        (serial, plan, is_active, expire_at, device_hash, activated_at)
    """
    device_hash = (device_hash or "").strip()
    if not device_hash:
        return None

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT serial, plan, is_active, expire_at, device_hash, activated_at
            FROM serials
            WHERE device_hash = ? AND is_active = 1
            ORDER BY issued_at DESC
            LIMIT 1
            """,
            (device_hash,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def list_serials() -> List[Tuple]:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT serial, plan, is_active, issued_at, expire_at, revoked_at, device_hash, activated_at, last_seen_at
            FROM serials
            ORDER BY issued_at DESC
            """
        )
        return cur.fetchall()
    finally:
        conn.close()


def deactivate(serial: str, revoked_at: str):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE serials
            SET is_active = 0, revoked_at = ?
            WHERE serial = ?
            """,
            (revoked_at, serial),
        )
        conn.commit()
    finally:
        conn.close()


def update_serial(
    serial: str,
    plan: str | None = None,
    expire_at: str | None = None,
):
    conn = _get_conn()
    try:
        cur = conn.cursor()

        fields = []
        params = []
        if plan is not None:
            fields.append("plan = ?")
            params.append(plan)
        if expire_at is not None:
            fields.append("expire_at = ?")
            params.append(expire_at)
        if not fields:
            return

        params.append(serial)
        sql = f"UPDATE serials SET {', '.join(fields)} WHERE serial = ?"
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def bind_device(serial: str, device_hash: str, activated_at: str):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE serials
            SET device_hash = ?, activated_at = ?, last_seen_at = ?
            WHERE serial = ?
            """,
            (device_hash, activated_at, activated_at, serial),
        )
        conn.commit()
    finally:
        conn.close()


def touch(serial: str, last_seen_at: str):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE serials
            SET last_seen_at = ?
            WHERE serial = ?
            """,
            (last_seen_at, serial),
        )
        conn.commit()
    finally:
        conn.close()


def reset_device_binding(serial: str):
    """기기 바인딩 초기화(관리자용)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE serials
            SET device_hash = NULL, activated_at = NULL
            WHERE serial = ?
            """,
            (serial,),
        )
        conn.commit()
    finally:
        conn.close()
