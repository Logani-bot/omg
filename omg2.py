#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OMG Phase 1 — Coin Top30 데일리 감시 (3년 ‘고가’ 기준 · 엑셀 출력)
=================================================================

목표 (이번 버전)
- CoinGecko API로 시총 Top 30 목록 수집 (심볼 풀)
- **바이낸스(Binance) 1d klines의 ‘고가(high)’ 기준으로 최근 3년 고점(H_3y_high) 계산**
  (바이낸스에 해당 USDT 페어가 없으면 스킵, **폴백 없음**)
- 각 코인에 대해 H_3y_high 기준 **매수선(B1~B7)·손절선(Stop)** 산출
- **엑셀(xlsx)로 저장** (CONFIG에 예산 항목 포함 → 배분 금액 자동 산출)

주의
- 사이클 H(98.5% / -44%) 로직은 이번 버전에서 **사용하지 않음**. 요청에 따라 **3년 ‘고가’의 단순 최대값**을 H로 사용.
- ‘창의 맨앞 상태가 high일 때 추가 확장’ 같은 백필(히스토리 확장) 로직 **미적용**.

확장성 (미래 계획)
- Phase 1.5: 텔레그램/Make 알림, Top30 자동 편입/탈락 감지
- Phase 2: 필요한 경우 사이클 H 로직(98.5%/-44%) 재도입
- Google Sheets 연동은 **데이터 모델 동일** → 출력 Writer만 추가하면 됨
  (구조 변경 거의 없음, 엑셀 컬럼/시트 구조 그대로 사용 가능)

의존 라이브러리
- requests
- openpyxl
    pip install requests openpyxl

Author: GPT
Version: 1.2.2
"""
from __future__ import annotations
import time
import pathlib
import datetime as dt
from typing import Any, Dict, List

import requests
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

# ====== CONFIG ======
VS_CURRENCY = "usd"          # 가격 통화 (usd 권장)
TOP_N = 30                    # 코인 상위 N개 (심볼 풀)
YEARS = 3                     # 3년
REQUEST_SLEEP_SEC = 0.8       # API Rate Limit 여유 시간
TIMEOUT_SEC = 20

# 예산 설정 (엑셀 CONFIG 시트에 기본값으로 기록됨)
DEFAULT_BUDGET_PER_ASSET = 1000.0  # 각 자산당 배정 예산(USD)
ALLOC_PCTS = [10, 10, 10, 10, 20, 20, 20]  # 1~7차 매수 비중(%)

# 출력 경로
OUTPUT_DIR = pathlib.Path("./output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
XLSX_PATH = OUTPUT_DIR / "omg_phase1_levels.xlsx"

# ====== Endpoints ======
# 심볼 풀: CoinGecko
CG_BASE = "https://api.coingecko.com/api/v3"
URL_TOP = f"{CG_BASE}/coins/markets"
# 가격 히스토리: Binance 1d klines (USDT 마켓)
BINANCE_BASE = "https://api.binance.com"
URL_KLINES = f"{BINANCE_BASE}/api/v3/klines"
URL_EXCHANGE_INFO = f"{BINANCE_BASE}/api/v3/exchangeInfo"

# ====== HTTP ======
def http_get(url: str, params: Dict[str, Any]) -> Any:
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SEC)
            if resp.status_code == 200:
                return resp.json()
            time.sleep(2 + attempt)
        except requests.RequestException:
            time.sleep(2 + attempt)
    raise RuntimeError(f"GET failed: {url} params={params}")

# ====== Data Fetch ======
def get_top_coins(vs_currency: str = VS_CURRENCY, top_n: int = TOP_N) -> List[Dict[str, Any]]:
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": top_n,
        "page": 1,
        "price_change_percentage": "24h",
        "locale": "en",
    }
    data = http_get(URL_TOP, params)
    coins = []
    for i, row in enumerate(data, start=1):
        coins.append({
            "rank": i,
            "id": row.get("id"),
            "symbol": (row.get("symbol") or "").upper(),
            "name": row.get("name"),
            "market_cap": row.get("market_cap"),
            "current_price": row.get("current_price"),
        })
    return coins


def get_binance_usdt_symbol_set() -> set[str]:
    """Binance의 USDT 마켓 심볼 집합(상태 TRADING) 로드.
    - 예: {"BTCUSDT", "ETHUSDT", ...}
    """
    data = http_get(URL_EXCHANGE_INFO, {})
    symbols = set()
    for s in data.get("symbols", []):
        try:
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                symbols.add(s.get("symbol"))
        except Exception:
            pass
    return symbols


def map_to_binance_symbol(symbol_upper: str, valid_usdt_symbols: set[str]) -> str | None:
    """CoinGecko symbol → Binance USDT 페어 심볼. 없으면 None.
    - 기본 규칙: <SYMBOL>USDT
    - 유효성: exchangeInfo로 받은 집합에 존재해야 함
    """
    candidate = f"{symbol_upper}USDT"
    return candidate if candidate in valid_usdt_symbols else None


def get_binance_1d_highs_3y(binance_symbol: str) -> List[float]:
    now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
    three_years_ago = dt.datetime.utcnow() - dt.timedelta(days=365*YEARS)
    start_ms = int(three_years_ago.timestamp() * 1000)

    highs: List[float] = []
    cur_start = start_ms
    while True:
        params = {
            "symbol": binance_symbol,
            "interval": "1d",
            "startTime": cur_start,
            "endTime": now_ms,
            "limit": 1000,
        }
        data = http_get(URL_KLINES, params)
        if not isinstance(data, list) or not data:
            break
        for k in data:
            try:
                high = float(k[2])
                highs.append(high)
            except Exception:
                pass
        last_close_time = int(data[-1][6])
        if last_close_time >= now_ms:
            break
        cur_start = last_close_time + 1
        if len(highs) > 1200:
            break
        time.sleep(0.2)

    if not highs:
        raise RuntimeError(f"No klines for {binance_symbol}")
    return highs

# ====== Core Logic (이번 버전: 3년 ‘고가’의 최대값) ======
def compute_three_year_high(highs: List[float]) -> float:
    return max(highs)


def compute_levels(H: float) -> Dict[str, float]:
    return {
        "B1": round(H * 0.56, 6),
        "B2": round(H * 0.52, 6),
        "B3": round(H * 0.46, 6),
        "B4": round(H * 0.41, 6),
        "B5": round(H * 0.35, 6),
        "B6": round(H * 0.28, 6),
        "B7": round(H * 0.21, 6),
        "Stop": round(H * 0.19, 6),
    }

# ====== Excel Writer ======
def autosize(ws):
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)


def write_excel(top_rows: List[Dict[str, Any]], level_rows: List[Dict[str, Any]], skipped_rows: List[Dict[str, Any]]):
    wb = Workbook()

    ws_conf = wb.active
    ws_conf.title = "CONFIG"
    ws_conf.append(["Key", "Value", "Note"])
    ws_conf.append(["BudgetPerAsset(USD)", DEFAULT_BUDGET_PER_ASSET, "각 자산별 기본 예산"])
    ws_conf.append(["AllocPercents(1~7)", ",".join(map(str, ALLOC_PCTS)), "매수 비중(%)"])
    autosize(ws_conf)

    ws_top = wb.create_sheet("COIN_TOP30")
    ws_top.append(["Rank", "Coin ID", "Symbol", "Name", "MarketCap", "CurrentPrice"])
    for r in top_rows:
        ws_top.append([
            r.get("rank"), r.get("id"), r.get("symbol"), r.get("name"),
            r.get("market_cap"), r.get("current_price")
        ])
    autosize(ws_top)

    ws_lvl = wb.create_sheet("LEVELS")
    headers = [
        "Date", "Coin ID", "Symbol", "Name", "H(3y_high)",
        "B1(-44%)", "B2(-48%)", "B3(-54%)", "B4(-59%)", "B5(-65%)", "B6(-72%)", "B7(-79%)", "Stop(-81%)",
        "Alloc%1", "Alloc%2", "Alloc%3", "Alloc%4", "Alloc%5", "Alloc%6", "Alloc%7",
        "BudgetPerAsset(USD)", "AllocAmt1", "AllocAmt2", "AllocAmt3", "AllocAmt4", "AllocAmt5", "AllocAmt6", "AllocAmt7"
    ]
    ws_lvl.append(headers)

    today = dt.datetime.now().strftime("%Y-%m-%d")
    for r in level_rows:
        budget = r.get("BudgetPerAsset", DEFAULT_BUDGET_PER_ASSET)
        alloc_amts = [round(budget * pct / 100.0, 2) for pct in ALLOC_PCTS]
        ws_lvl.append([
            today, r.get("Coin ID"), r.get("Symbol"), r.get("Name"), r.get("H(3y_high)"),
            r.get("B1(-44%)"), r.get("B2(-48%)"), r.get("B3(-54%)"), r.get("B4(-59%)"),
            r.get("B5(-65%)"), r.get("B6(-72%)"), r.get("B7(-79%)"), r.get("Stop(-81%)"),
            *ALLOC_PCTS,
            budget, *alloc_amts
        ])
    autosize(ws_lvl)

    # SKIPPED 시트 (바이낸스 USDT 페어 없음/데이터 없음 등)
    ws_skip = wb.create_sheet("SKIPPED")
    ws_skip.append(["Rank", "Coin ID", "Symbol", "Name", "Reason"])
    for r in skipped_rows:
        ws_skip.append([r.get("rank"), r.get("id"), r.get("symbol"), r.get("name"), r.get("reason")])
    autosize(ws_skip)

    wb.save(XLSX_PATH)
    return XLSX_PATH

# ====== Main ======
def main():
    today = dt.datetime.now().strftime("%Y-%m-%d")

    print("[1/4] 시총 Top 30 조회…")
    coins = get_top_coins(vs_currency=VS_CURRENCY, top_n=TOP_N)
    print(f" - {len(coins)}개 수집")

    print("[2/4] Binance USDT 심볼 목록 로드…")
    valid_usdt_symbols = get_binance_usdt_symbol_set()
    print(f" - 유효 USDT 심볼 {len(valid_usdt_symbols)}개")

    top_rows = coins

    print("[3/4] 각 코인별 3년 ‘고가’ 기반 H 계산 및 레벨 산출…")
    level_rows: List[Dict[str, Any]] = []
    skipped_rows: List[Dict[str, Any]] = []
    for idx, c in enumerate(coins, start=1):
        sym_u = c["symbol"]
        binance_sym = map_to_binance_symbol(sym_u, valid_usdt_symbols)

        if sym_u in {"USDT", "USDC", "USDS", "DAI", "TUSD", "FDUSD", "USDE"}:
            skipped_rows.append({"rank": c["rank"], "id": c["id"], "symbol": sym_u, "name": c["name"], "reason": "stable"})
            print(f" - [{idx:02d}] {sym_u.lower():<6} 스킵(스테이블)")
            time.sleep(REQUEST_SLEEP_SEC)
            continue

        if binance_sym is None:
            skipped_rows.append({"rank": c["rank"], "id": c["id"], "symbol": sym_u, "name": c["name"], "reason": "no USDT pair on Binance"})
            print(f" ! [{idx:02d}] {sym_u.lower():<6} 스킵 — Binance USDT 페어 없음")
            time.sleep(REQUEST_SLEEP_SEC)
            continue

        try:
            highs = get_binance_1d_highs_3y(binance_sym)
            H = compute_three_year_high(highs)
            lvl = compute_levels(H)
            level_rows.append({
                "Coin ID": c["id"],
                "Symbol": sym_u,
                "Name": c["name"],
                "H(3y_high)": round(H, 6),
                "B1(-44%)": lvl["B1"],
                "B2(-48%)": lvl["B2"],
                "B3(-54%)": lvl["B3"],
                "B4(-59%)": lvl["B4"],
                "B5(-65%)": lvl["B5"],
                "B6(-72%)": lvl["B6"],
                "B7(-79%)": lvl["B7"],
                "Stop(-81%)": lvl["Stop"],
            })
            print(f" - [{idx:02d}] {sym_u.lower():<6} H(3y_high)={H:.6f}")
        except Exception as e:
            skipped_rows.append({"rank": c["rank"], "id": c["id"], "symbol": sym_u, "name": c["name"], "reason": str(e)[:160]})
            print(f" ! [{idx:02d}] {sym_u.lower():<6} 스킵/실패 — {e}")
        time.sleep(REQUEST_SLEEP_SEC)

    print("[4/4] 엑셀 저장…")
    path = write_excel(top_rows, level_rows, skipped_rows)
    print(f" - 저장완료: {path}")

if __name__ == "__main__":
    main()
