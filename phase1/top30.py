#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1 (MVP): 시총 Top 30 코인만 선별
- 5년 고점, 매수선, 비중 계산 등 제거
- 예외: 파생 / wrapped / 브리지 / 레버리지(UP/DOWN, 3L/3S, BULL/BEAR) / 스테이블(USDC, USDT, USDE 등) 제외
- Binance 현물 USDT 페어(TRADING) 검증 후 최종 30개 반환/저장

사용 예:
python -u phase1/top30.py --out ./data/top_30_coins.csv --n 30
"""
import argparse
import sys
from typing import Dict, List
import pandas as pd
import requests

BINANCE_BASE = "https://api.binance.com"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
QUOTE_ASSET = "USDT"

# -----------------------------
# CoinGecko TopN
# -----------------------------

def coingecko_top_coins(n: int = 50) -> pd.DataFrame:
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": n,
        "page": 1,
        "sparkline": "false",
        "locale": "en",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    rows = []
    for x in data:
        rows.append({
            "id": x.get("id"),
            "symbol": (x.get("symbol") or "").upper(),
            "name": x.get("name"),
            "market_cap": x.get("market_cap"),
        })
    return pd.DataFrame(rows)

# -----------------------------
# Exclusions
# -----------------------------

def _exclude_wrapped_bridge_derivatives(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    def bad_text(s: str) -> bool:
        if not s:
            return False
        s = s.lower()
        patterns = [
            "wrapped", "bridge", "bridged", "pegged", "wormhole", "portal"
        ]
        return any(p in s for p in patterns)
    def bad_symbol(sym: str) -> bool:
        if not sym:
            return False
        su = sym.upper()
        # 대표 wrapped: WBTC/WETH 등 (W + 2~4자) — 과도 배제 시 완화 가능
        if su.startswith("W") and 2 <= len(su) <= 5:
            return True
        return False
    m = (
        df["name"].map(bad_text) |
        df["id"].map(bad_text) |
        df["symbol"].map(bad_symbol)
    )
    return df[~m].copy()


def _exclude_leverage_tokens(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    def is_leverage_symbol(sym: str) -> bool:
        if not sym:
            return False
        su = sym.upper()
        # Binance 레버리지 토큰 패턴: UP/DOWN, 3L/3S, 5L/5S, BULL/BEAR 등
        key_pairs = ["UP", "DOWN", "BULL", "BEAR", "3L", "3S", "5L", "5S"]
        return any(su.endswith(k) or su.startswith(k) for k in key_pairs)
    m = df["symbol"].map(is_leverage_symbol)
    return df[~m].copy()


def _exclude_stablecoins(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    stable_list = ["USDC", "USDT", "USDE", "DAI", "TUSD", "FDUSD", "USDS", "PYUSD", "BUSD"]
    mask = df["symbol"].isin(stable_list)
    return df[~mask].copy()

# -----------------------------
# Binance 검증
# -----------------------------

def binance_exchange_info() -> Dict[str, dict]:
    url = f"{BINANCE_BASE}/api/v3/exchangeInfo"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    return {s["symbol"]: s for s in data.get("symbols", []) if s.get("status") == "TRADING"}


def plausible_binance_symbols(df: pd.DataFrame, quote: str = QUOTE_ASSET) -> pd.DataFrame:
    df = df.copy()
    df["binance_symbol"] = df["symbol"].str.upper().str.replace(".", "", regex=False) + quote
    return df

# -----------------------------
# Public API
# -----------------------------

def get_top30_binance(n_source: int = 80) -> pd.DataFrame:
    """CoinGecko Top n_source → 제외 필터 → Binance(TRADING & USDT) 검증 → Top 30."""
    cg = coingecko_top_coins(n_source)
    cg = _exclude_wrapped_bridge_derivatives(cg)
    cg = _exclude_leverage_tokens(cg)
    cg = _exclude_stablecoins(cg)
    cg = plausible_binance_symbols(cg, QUOTE_ASSET)

    info = binance_exchange_info()
    cg["binance_ok"] = cg["binance_symbol"].map(lambda s: s in info)
    df_ok = cg[cg["binance_ok"]].copy()
    df_ok = df_ok.sort_values("market_cap", ascending=False).head(30)
    return df_ok[["symbol", "name", "binance_symbol", "market_cap"]].reset_index(drop=True)

# -----------------------------
# CLI
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="./data/top_30_coins.csv")
    ap.add_argument("--n-source", type=int, default=80, help="CoinGecko에서 불러올 상위 개수(필터 전)")
    args = ap.parse_args()

    df = get_top30_binance(args.n_source)
    out = args.out
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)
    print("Saved:", out)
    print(df.head())

if __name__ == "__main__":
    main()