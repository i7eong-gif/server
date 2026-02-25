from __future__ import annotations

import os
from pathlib import Path

# -------------------------------------------------
# 1. 프로젝트 루트
# -------------------------------------------------
# app/core/config.py 기준
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# -------------------------------------------------
# 2. 실행 환경
# -------------------------------------------------
ENV = os.getenv("ENV", "dev").lower()
DEBUG = ENV != "prod"

# -------------------------------------------------
# 3. 데이터 디렉터리
# -------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# 4. DB 경로 (런타임 결정)
# -------------------------------------------------
DEFAULT_DB_PATH = str(DATA_DIR / "app.db")


def get_db_path() -> str:
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


# -------------------------------------------------
# 5. Admin Token
# -------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "4165")
