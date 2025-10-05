#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2.0 — 원클릭 요약 시스템 (Final MVP)
- Phase 1 (top30) + Phase 1.5 (core simulation) 통합 오케스트레이터
- 실행: Top30 자동 선정 → OHLC 수집 → Phase 1.5 분석 → Snapshot CSV
"""

import argparse
import concurrent.futures as futures
import datetime as dt
import os
import sys
from typing import List, Optional

import pandas as pd

# --- Import 기존 Phase1, Phase1.5 ---
try:
    from core.phase1_5_core import run_phase1_5_simulation, get_binance_1d_ohlc_5y
    from phase1.top30 import get_top30_binance
except Exception as e:
    print("[ERROR] core/phase1_5_core or phase1/top30 import failed:", e, file=sys.stderr)
    raise

# --- 상수 ---
ROUND_PRICE = 6
ROUND_PCT = 3
DEFAULT_LOOKBACK = 365


def now_seoul_date_str() -> str:
    """Asia/Seoul 기준 YYYYMMDD 문자열."""
    return dt.datetime.now().strftime("%Y%m%d")


# ---------------------------------------
# 코인별 Phase 1.5 실행 및 요약 생성
# ---------------------------------------
def analyze_symbol(binance_symbol: str, name: str, lookback_days: int) -> Optional[dict]:
    try:
        # 1) OHLC 원본 포맷 확보 (코어가 기대하는 dict 리스트)
        rows = get_binance_1d_ohlc_5y(binance_symbol)
        if not rows:
            raise ValueError(f"No OHLC rows for {binance_symbol}")

        # 2) seed_H: 관측 구간 최대 high
        seed_H = max(float(r["high"]) for r in rows if r.get("high") is not None)

        # 3) shadow CSV 경로
        os.makedirs("./output/shadow", exist_ok=True)
        out_csv = f"./output/shadow/{binance_symbol}_phase1_5_shadow_{now_seoul_date_str()}.csv"

        # 4) Phase 1.5 코어 실행 (shadow CSV 생성 담당)
        run_phase1_5_simulation(
            symbol=binance_symbol,
            ohlc=rows,
            seed_H=seed_H,
            out_csv=out_csv,
            limit_days=lookback_days,
            daily_H=None,
        )

        # 5) shadow CSV 마지막 데이터 행 읽기 (open() 사용)
        with open(out_csv, encoding="utf-8") as f:
            lines = f.read().splitlines()

        header, last_parts = None, None
        for ln in reversed(lines):
            parts = ln.split(",")
            if not parts:
                continue
            if parts[0] == "date":
                header = parts
                break
            if last_parts is None:
                last_parts = parts

        if not header or not last_parts:
            raise ValueError("Shadow CSV malformed: header/last row not found")

        idx = {k: i for i, k in enumerate(header)}

        def g(key, cast=float, default=None):
            try:
                v = last_parts[idx[key]] if key in idx and idx[key] < len(last_parts) else None
                if v in (None, "", "None"):
                    return default
                return cast(v) if cast else v
            except Exception:
                return default

        last_price = g("close")
        mode = g("mode", cast=str)
        stage = g("stage", cast=lambda x: int(x) if x not in ("", "None") else 0, default=0)
        next_buy_level = g("next_buy_level_name", cast=str, default="-")
        next_buy_price = g("next_buy_level_price")
        H = g("H")
        L_now = g("L_now")
        rebound_from_L = g("rebound_from_L_pct")
        cutoff = g("cutoff_price")

        # 6) 파생 계산
        pct_to_next, pct_to_next_abs, drawdown_from_H = None, None, None
        if last_price and next_buy_price:
            pct_to_next = (next_buy_price - last_price) / last_price * 100
            pct_to_next_abs = abs(pct_to_next)
        if last_price and H and H != 0:
            drawdown_from_H = (last_price / H - 1) * 100

        rec = {
            "universe": "COIN",
            "symbol": binance_symbol,
            "name": name,
            "last_price": round(last_price, ROUND_PRICE) if last_price else None,
            "mode": mode,
            "in_position": "Y" if (stage or 0) > 0 else "N",
            "stage": stage or 0,
            "next_buy_level": next_buy_level,
            "next_buy_price": round(next_buy_price, ROUND_PRICE) if next_buy_price else None,
            "pct_to_next_buy": round(pct_to_next, ROUND_PCT) if pct_to_next is not None else None,
            "pct_to_next_buy_abs": round(pct_to_next_abs, ROUND_PCT) if pct_to_next_abs is not None else None,
            "H": round(H, ROUND_PRICE) if H else None,
            "L_now": round(L_now, ROUND_PRICE) if L_now else None,
            "drawdown_from_H_pct": round(drawdown_from_H, ROUND_PCT) if drawdown_from_H is not None else None,
            "rebound_from_L_pct": round(rebound_from_L, ROUND_PCT) if rebound_from_L is not None else None,
            "buy_allowed_today": None,
            "sell_restricted": None,
            "notes": ("cutoff" if cutoff is not None else None),
        }
        return rec

    except Exception as e:
        return {
            "universe": "COIN",
            "symbol": binance_symbol,
            "name": name,
            "error": str(e),
        }


# ---------------------------------------
# 메인: 병렬 실행 및 스냅샷 생성
# ---------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--max-workers", type=str, default="auto")
    args = ap.parse_args()

    out_path = args.out or os.path.join("./output", f"coins_snapshot_{now_seoul_date_str()}.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 1) Top30 불러오기 (Phase 1)
    print("[1/4] Selecting Top30 via Phase 1 (MVP: Top30 Only, with exclusions)...")
    df_top = get_top30_binance(n_source=80)
    print(df_top.head())

    # 2) 병렬 실행
    items = list(df_top.itertuples(index=False))
    max_workers = os.cpu_count() - 1 if args.max_workers == "auto" else int(args.max_workers)
    max_workers = max(1, max_workers)

    print(f"[2/4] Fetching klines & Analyzing via Phase 1.5... (workers={max_workers})")
    recs: List[dict] = []
    with futures.ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(analyze_symbol, row.binance_symbol, row.name, args.lookback_days) for row in items]
        for fut in futures.as_completed(futs):
            rec = fut.result()
            if rec:
                recs.append(rec)

    # 3) 스냅샷 CSV 생성
    print("[3/4] Building snapshot DataFrame...")
    df = pd.DataFrame(recs)

    if not df.empty:
        if "error" in df.columns:
            df_ok = df[df["error"].isna()].copy()
            df_err = df[df["error"].notna()].copy()
        else:
            df_ok, df_err = df.copy(), pd.DataFrame(columns=df.columns)

        if not df_ok.empty:
            df_ok = df_ok.sort_values(["pct_to_next_buy_abs", "symbol"], ascending=[True, True], na_position="last")
        df = pd.concat([df_ok, df_err], ignore_index=True)

    # 4) 저장
    print(f"[4/4] Saving → {out_path}")
    df.to_csv(out_path, index=False)
    print("Done.")
    if not df_err.empty:
        print(f"⚠️ Errors for {len(df_err)} symbols:")
        print(df_err[["symbol", "error"]].head())


if __name__ == "__main__":
    main()
