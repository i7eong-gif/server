# KRStockTray/
# ├─ main.py                 엔트리
# ├─ app.py                  앱의 심장 (대부분 여기)
# ├─ providers.py             시세 조회 전용
# ├─ tickers/
# │  ├─ __init__.py
# │  └─ loader.py             종목명 검색 (오프라인)

from app import StockTrayApp

if __name__ == "__main__":
    StockTrayApp().run()