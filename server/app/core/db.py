"""
DB Initialization / Migration

역할:
- serials 테이블 스키마를 "단일 정답"으로 보장

원칙:
- 서버 startup 시 항상 호출됨 (main.py)
- import 시 부작용 없음
"""

from __future__ import annotations

import psycopg2
from app.core.config import DATABASE_URL


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    _ensure_serials_table(cur)
    conn.commit()
    conn.close()


def _ensure_serials_table(cur) -> None:
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'serials'
        """
    )
    if cur.fetchone() is not None:
        return

    cur.execute(
        """
        CREATE TABLE serials (
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
    )
    cur.execute("CREATE INDEX idx_serials_active ON serials(is_active)")
    cur.execute("CREATE INDEX idx_serials_expire ON serials(expire_at)")
