# ============================================================
# File: universe_selector.py
# ------------------------------------------------------------
# ✅ 역할:
#   - 모든 분석의 출발점 (자산 리스트 관리)
#   - 코인(CoinGecko 시가총액 Top30) / 미국주식(Top200 CSV) 리스트 생성
#
# ✅ 실행 예시:
#   python universe_selector.py --asset coin --save
#   python universe_selector.py --asset us --save
#
# ✅ 출력 항목:
#   순위 / 종목명(Symbol) / 시가총액(USD)
# ============================================================

from typing import List, Tuple, Dict, Any
import requests
import os
import time

try:
    import pandas as pd
except Exception:
    pd = None


# -----------------------------
# 공통 설정
# -----------------------------
VS_CURRENCY = "usd"
TOP_N = 100
URL_TOP = "https://api.coingecko.com/api/v3/coins/markets"

EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH", "USD1", "BFUSD", "BNSOL", "BNB", "ENA"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}


# -----------------------------
# HTTP 안정 호출 (omg2 기반)
# -----------------------------
def http_get(url: str, params: dict) -> list:
    headers = {"User-Agent": "Mozilla/5.0"}
    backoff = 1.0
    for _ in range(6):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(backoff)
                backoff = min(backoff * 1.8, 10)
                continue
            print(f"[HTTP {resp.status_code}] {resp.text[:100]}")
            return []
        except requests.RequestException:
            time.sleep(backoff)
            backoff = min(backoff * 1.8, 10)
    return []


# -----------------------------
# 코인: CoinGecko 기준 시가총액 Top 30
# -----------------------------
def get_top30_coins() -> List[Dict[str, Any]]:
    """CoinGecko 기준 시가총액 Top 100 코인 + CSV 저장"""
    coins = []
    page = 1
    per_page = 100  # CoinGecko API 한 번에 최대 250개까지 가능
    
    # 필터링 후 TOP_N개 수집될 때까지 반복
    while len(coins) < TOP_N:
        params = {
            "vs_currency": VS_CURRENCY,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "price_change_percentage": "24h",
            "locale": "en",
        }

        data = http_get(URL_TOP, params)
        if not data or not isinstance(data, list):
            print(f"CoinGecko page {page} failed")
            break
        
        if len(data) == 0:
            break

        for row in data:
            try:
                cap_raw = row.get("market_cap", 0)
                if isinstance(cap_raw, str):
                    cap_raw = cap_raw.replace(",", "").strip()
                cap = float(cap_raw)
            except Exception:
                cap = 0.0

            sym = (row.get("symbol") or "").upper() + "USDT"
            name = row.get("name", "")

            # 제외 조건
            if sym.replace("USDT", "") in EXCLUDE_SYMBOLS:
                continue
            if any(k in name.upper() for k in EXCLUDE_NAME_KEYWORDS):
                continue

            rank = row.get("market_cap_rank", len(coins) + 1)
            coins.append({
                "Rank": rank,
                "Symbol": sym,
                "Name": name,
                "MarketCap(USD)": round(cap, 2)
            })
            
            # TOP_N개 수집되면 중단
            if len(coins) >= TOP_N:
                break
        
        page += 1
        
        # 최대 3페이지까지만 시도 (300개)
        if page > 3:
            break

    # CSV 저장
    os.makedirs("debug", exist_ok=True)
    csv_path = os.path.join("debug", "top_list_coin.csv")
    if pd:
        pd.DataFrame(coins).to_csv(csv_path, index=False)
    else:
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Rank", "Symbol", "Name", "MarketCap(USD)"])
            writer.writeheader()
            writer.writerows(coins)
    print(f"Coin Top{TOP_N} list saved: {csv_path}")
    return coins


# -----------------------------
# 미국 주식: Top 200 (CSV/XLSX에서 로드)
# -----------------------------
def get_top200_us_stocks(path: str | None = None) -> List[Dict[str, Any]]:
    if pd is None:
        raise RuntimeError("pandas가 필요합니다. pip install pandas")

    cands = []
    if path:
        cands.append(path)
    cands += ["top_200_us_stocks.xlsx", "top_200_us_stocks.csv"]
    file = next((p for p in cands if os.path.exists(p)), None)
    if not file:
        raise FileNotFoundError("미국 주식 리스트(top_200_us_stocks.csv/.xlsx)가 필요합니다. 컬럼명: Symbol, MarketCap")

    if file.lower().endswith(".xlsx"):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    cols = {c.lower(): c for c in df.columns}
    sym_col = cols.get("symbol")
    cap_col = cols.get("marketcap")
    if not sym_col or not cap_col:
        raise ValueError("파일에 'Symbol'과 'MarketCap' 컬럼이 필요합니다.")

    df = df[[sym_col, cap_col]].dropna()
    df = df.sort_values(cap_col, ascending=False).head(200)

    stocks = []
    for i, row in enumerate(df.itertuples(index=False), start=1):
        sym = str(getattr(row, sym_col)).strip().upper()
        cap = float(getattr(row, cap_col))
        stocks.append({
            "Rank": i,
            "Symbol": sym,
            "Name": sym,
            "MarketCap(USD)": round(cap, 2)
        })
    return stocks


def get_top30_symbols() -> List[str]:
    """Top 30 코인의 심볼 리스트만 반환 (USDT 포함)"""
    coins = get_top30_coins()
    return [coin["Symbol"] for coin in coins]


# -----------------------------
# 통합 인터페이스
# -----------------------------
def get_universe(asset: str = "coin"):
    if asset == "coin":
        return get_top30_coins()
    elif asset == "us":
        return get_top200_us_stocks()
    else:
        raise ValueError("asset은 'coin' 또는 'us'만 허용합니다.")


# -----------------------------
# 실행부
# -----------------------------
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", choices=["coin", "us"], default="coin")
    args = ap.parse_args()

    data = get_universe(args.asset)

    print("=" * 60)
    print(f"{args.asset.upper()} 리스트 ({len(data)}개)")
    print("순위 | 심볼 | 시가총액(USD)")
    print("-" * 60)

    if not data:
        print("⚠️  데이터가 없습니다.")
    else:
        for row in data:
            print(f"{row['Rank']:>3} | {row['Symbol']:<10} | {row['MarketCap(USD)']:,.0f}")
