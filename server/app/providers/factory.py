from app.providers.kr.kr_provider import KRProvider
from app.providers.us.us_provider import USProvider
from app.core.exceptions import InvalidMarketError

def get_provider(market: str):
    market = market.upper()
    if market == "KR":
        return KRProvider()
    if market == "US":
        return USProvider()
    raise InvalidMarketError(market)


# =========================================================
# 🧪 단독 실행 테스트 (Factory 레벨)
# =========================================================

if __name__ == "__main__":
    from app.providers.base import QuoteProvider
    from pprint import pprint

    print("=== Provider Factory Test ===")

    # 1️⃣ KR Provider 생성 테스트
    kr = get_provider("KR")
    print("\n[KR]")
    print("Instance:", kr)
    assert isinstance(kr, KRProvider)

    ctx = kr.init_context("005930")
    result = kr.poll(ctx)
    pprint(result)

    # 2️⃣ US Provider 생성 테스트
    us = get_provider("US")
    print("\n[US]")
    print("Instance:", us)
    assert isinstance(us, USProvider)

    ctx = us.init_context("AAPL")
    result = us.poll(ctx)
    pprint(result)

    # 3️⃣ 잘못된 market 처리
    print("\n[INVALID MARKET]")
    try:
        get_provider("JP")
        raise AssertionError("Expected ValueError not raised")
    except ValueError as e:
        print("Caught expected exception:", e)

    print("\n✅ Provider Factory test PASSED")