from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import List, Dict, Optional

import FinanceDataReader as fdr


@dataclass(frozen=True)
class KrSymbol:
    code: str
    name: str
    market: str   # KRX / ETF


class KrxSymbolProvider:
    def __init__(self, ttl_sec: int = 24 * 3600):
        self.ttl_sec = ttl_sec
        self._lock = threading.Lock()
        self._loaded_at = 0.0
        self._symbols: Dict[str, KrSymbol] = {}  # code → KrSymbol (O(1) 조회)

    def _fetch_from_fdr(self) -> Dict[str, KrSymbol]:
        out: Dict[str, KrSymbol] = {}

        # -----------------
        # 1) KRX 상장사
        # -----------------
        df_krx = fdr.StockListing("KRX")

        for _, r in df_krx.iterrows():
            if "Code" not in r or "Name" not in r:
                continue

            code = str(r["Code"]).zfill(6)
            name = str(r["Name"]).strip()

            if not code or not name:
                continue

            out[code] = KrSymbol(
                code=code,
                name=name,
                market="KRX",
            )

        # -----------------
        # 2) 국내 ETF
        # -----------------
        df_etf = fdr.StockListing("ETF/KR")

        for _, r in df_etf.iterrows():
            if "Code" not in r or "Name" not in r:
                continue

            code = str(r["Code"]).zfill(6)
            name = str(r["Name"]).strip()

            if not code or not name:
                continue

            out[code] = KrSymbol(
                code=code,
                name=name,
                market="ETF",
            )

        return out

    def ensure_loaded(self) -> None:
        now = time.time()
        if self._symbols and (now - self._loaded_at) < self.ttl_sec:
            return

        with self._lock:
            now = time.time()
            if self._symbols and (now - self._loaded_at) < self.ttl_sec:
                return

            self._symbols = self._fetch_from_fdr()
            self._loaded_at = now

    def get_all(self) -> List[KrSymbol]:
        self.ensure_loaded()
        return list(self._symbols.values())

    def updated_at(self) -> float:
        return self._loaded_at

    def get_symbol(self, code: str) -> Optional[KrSymbol]:
        self.ensure_loaded()
        return self._symbols.get(code.zfill(6))

    def get_name(self, code: str) -> Optional[str]:
        sym = self.get_symbol(code)
        return sym.name if sym else None

PROVIDER = KrxSymbolProvider(
    ttl_sec=24 * 3600
)
