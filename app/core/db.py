"""
DB Initialization / Migration

역할:
- SQLite DB 파일 존재 보장
- serials 테이블 스키마를 "단일 정답"으로 보장

원칙:
- 서버 startup 시 항상 호출됨 (main.py)
- import 시 부작용 없음
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import get_db_path


def init_db() -> None:
    """
    DB 초기화 및 스키마 보장
    """
    db_path = Path(get_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        get_db_path(),
        timeout=30,
        check_same_thread=False,
    )
    cur = conn.cursor()

    # -------------------------------------------------
    # serials 테이블(라이선스/시리얼) 스키마 보장
    # -------------------------------------------------
    _ensure_serials_table(cur)

    conn.commit()
    conn.close()


def _ensure_serials_table(cur: sqlite3.Cursor) -> None:
    """serials 테이블이 없으면 생성한다."""
    cur.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='serials'
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

