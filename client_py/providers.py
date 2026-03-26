import requests
from typing import Optional, Tuple
import logging
from bs4 import BeautifulSoup
from datetime import datetime, time
import pytz

KST = pytz.timezone("Asia/Seoul")

class QuoteProviderKR:
    """
    NAVER sise.nhn 전용 Provider
    반환값: (price, prev_close, total_volume)
    """

    NAVER_SISE_URL = "https://finance.naver.com/item/sise.naver"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.naver.com/",
        }

    # -------------------------------------------------
    # 장중 여부
    # -------------------------------------------------
    @staticmethod
    def _is_regular_market(now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(KST)
        t = now.time()
        return time(9, 1) <= t <= time(15, 19) 

    # -------------------------------------------------
    # 외부 호출
    # -------------------------------------------------
    def get_quote(
        self,
        code: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tuple[int, int, int]]:

        try:
            r = self.session.get(
                self.NAVER_SISE_URL,
                params={"code": code},
                headers=self.headers,
                timeout=3,
            )
            r.raise_for_status()

            # 네이버는 대부분 euc-kr
            r.encoding = r.apparent_encoding

            soup = BeautifulSoup(r.text, "html.parser")

            krx_block = soup.select_one("#rate_info_krx")
            nxt_block = soup.select_one("#rate_info_nxt")

            if not krx_block:
                return None

            # ============================
            # 1️⃣ 가격 선택
            # ============================
            use_nxt = False

            if self._is_regular_market(now):
                price = self._extract_price(krx_block)
            else:
                nxt_price = self._extract_price(nxt_block)
                if nxt_price:
                    price = nxt_price
                    use_nxt = True
                else:
                    price = self._extract_price(krx_block)

            if price is None:
                return None

            # ============================
            # 2️⃣ 전일가 (NXT 가격 사용 시 NXT 전일가, 아니면 KRX)
            # ============================
            prev_close = (
                self._extract_prev_close(nxt_block) or self._extract_prev_close(krx_block)
                if use_nxt
                else self._extract_prev_close(krx_block)
            )

            if prev_close is None:
                return None

            # ============================
            # 3️⃣ 거래량 합산
            # ============================
            krx_vol = self._extract_volume(krx_block)
            nxt_vol = self._extract_volume(nxt_block)

            total_volume = (krx_vol or 0) + (nxt_vol or 0)

            return price, prev_close, total_volume

        except Exception:
            logging.exception("KR sise parse failed")
            return None

    # -------------------------------------------------
    # price 추출
    # -------------------------------------------------
    def _extract_price(self, block) -> Optional[int]:
        if not block:
            return None
        tag = block.select_one(".today .no_today .blind")
        return self._to_int(tag.get_text()) if tag else None

    # -------------------------------------------------
    # 전일가 추출
    # -------------------------------------------------
    def _extract_prev_close(self, block) -> Optional[int]:
        if not block:
            return None

        for td in block.select("table.no_info td"):
            label = td.select_one("span.sptxt.sp_txt2")
            if label:
                tag = td.select_one(".blind")
                if tag:
                    return self._to_int(tag.get_text())
        return None

    # -------------------------------------------------
    # 거래량 추출
    # -------------------------------------------------
    def _extract_volume(self, block) -> int:
        if not block:
            return 0

        for td in block.select("table.no_info td"):
            label = td.select_one("span.sptxt.sp_txt9")
            if label:
                tag = td.select_one(".blind")
                if tag:
                    return self._to_int(tag.get_text()) or 0
        return 0

    # -------------------------------------------------
    # 숫자 변환
    # -------------------------------------------------
    @staticmethod
    def _to_int(v) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(
                str(v)
                .replace(",", "")
                .replace("+", "")
                .replace("▲", "")
                .replace("▼", "")
                .strip()
            )
        except Exception:
            return None


# =========================================================
# US Provider (Yahoo Chart API)
# =========================================================
class QuoteProviderUS:
    """
    US 시세 Provider (Yahoo Chart API 직접 호출)

    API:
    https://query1.finance.yahoo.com/v8/finance/chart/{symbol}

    return: (price, pct, volume)
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    def get_name(self, code: str) -> str:
        return (code or "").upper()

    def get_quote(
        self,
        code: str,
        now: Optional[datetime] = None,
    ) -> Optional[Tuple[float, float, int]]:
        try:
            r = self.session.get(
                self.BASE_URL.format(code),
                headers=self.headers,
                timeout=2,
            )
            r.raise_for_status()

            data = r.json()
            result = data["chart"]["result"]
            if not result:
                return None

            meta = result[0]["meta"]

            price = meta.get("regularMarketPrice")
            prev = meta.get("previousClose")
            volume = meta.get("regularMarketVolume")

            if price is None or prev in (None, 0):
                return None

            return (
                round(float(price), 2),
                round(float(prev), 2),
                int(volume or 0),
            )

        except Exception:
            logging.exception("US Yahoo Chart API failed")
            return None


# =========================================================
# TEST ROUTINE
# =========================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    kr = QuoteProviderKR()
    us = QuoteProviderUS()

    print("==== KR TEST ====")
    for code in ["005930", "411060", "035720"]:
        q = kr.get_quote(code)
        if q:
            price, prev, vol = q
            print(
                f"[KR {code}] "
                f"price={price:,} "
                f"prev={prev:,} "
                f"volume={vol:,}"
            )
        else:
            print(f"[KR {code}] FAILED")

    print("\n==== US TEST ====")
    for code in ["AAPL", "MSFT", "TQQQ"]:
        q = us.get_quote(code)
        if q:
            price, prev, vol = q
            print(
                f"[US {code}] "
                f"price={price} "
                f"prev={prev} "
                f"volume={vol:,}"
            )
        else:
            print(f"[US {code}] FAILED")