# generate_kr_tickers.py
import json
import FinanceDataReader as fdr


def get_code_col(df):
    for c in ("Symbol", "Code", "Ticker"):
        if c in df.columns:
            return c
    raise KeyError("종목코드 컬럼을 찾을 수 없습니다")


rows = {}

# =========================
# 1️⃣ KOSPI
# =========================
df_kospi = fdr.StockListing("KOSPI")
code_col = get_code_col(df_kospi)

for _, r in df_kospi.iterrows():
    code = str(r[code_col]).zfill(6)
    name = str(r["Name"]).strip()

    rows[code] = {
        "code": code,
        "name": name,
        "market": "KOSPI",
        "type": "STOCK",
        "yahoo": f"{code}.KS",
    }

print(f"KOSPI 종목 수: {len(rows)}")

# =========================
# 2️⃣ KOSDAQ
# =========================
df_kosdaq = fdr.StockListing("KOSDAQ")
code_col = get_code_col(df_kosdaq)

cnt_before = len(rows)

for _, r in df_kosdaq.iterrows():
    code = str(r[code_col]).zfill(6)
    name = str(r["Name"]).strip()

    rows[code] = {
        "code": code,
        "name": name,
        "market": "KOSDAQ",
        "type": "STOCK",
        "yahoo": f"{code}.KQ",
    }

print(f"KOSDAQ 종목 수: {len(rows) - cnt_before}")
print(f"KOSPI + KOSDAQ 합계: {len(rows)}")

# =========================
# 3️⃣ ETF (KR)
# =========================
df_etf = fdr.StockListing("ETF/KR")
code_col = get_code_col(df_etf)

cnt_before = len(rows)

for _, r in df_etf.iterrows():
    code = str(r[code_col]).zfill(6)
    name = str(r["Name"]).strip()

    # ETF는 대부분 KOSPI(.KS)로 매핑
    rows[code] = {
        "code": code,
        "name": name,
        "market": "KR",
        "type": "ETF",
        "yahoo": f"{code}.KS",
    }

print(f"ETF 수: {len(rows) - cnt_before}")
print(f"총 종목 수 (STOCK + ETF): {len(rows)}")

# =========================
# 4️⃣ 저장
# =========================
with open("kr.json", "w", encoding="utf-8") as f:
    json.dump(
        sorted(rows.values(), key=lambda x: x["code"]),
        f,
        ensure_ascii=False,
        indent=2,
    )

print("✅ kr.json 생성 완료")