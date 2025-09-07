#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Runner — Phase 1 기반 (원본 omg2.py 유지)
- Phase 1에서 확정된 고점 신호(H) 이후에만 매수/매도 로직 작동
- H 공급 방식 3가지 중 하나 택일
  (A) --seed-h : 직접 주입
  (B) --phase1-csv : Phase1 CSV에서 읽기 (cand_H/H/peak 등 컬럼)
  (C) --auto-phase1 : 내장 Phase1 로직으로 자동 탐지

출력: ./output/<symbol>_phase1_5_shadow.csv
"""

import argparse
import csv
import pathlib
import sys
import traceback
from typing import Optional

print("[RUNNER] module import start", flush=True)

from core.phase1_5_core import (
    ensure_output_dir,
    get_binance_1d_ohlc_5y,
    compute_phase1_peak_signal_H,
    run_phase1_5_simulation,
)

print("[RUNNER] core imported OK", flush=True)


def load_H_from_csv(csv_path: pathlib.Path) -> Optional[float]:
    print(f"[RUNNER] load_H_from_csv: {csv_path}", flush=True)
    cand_names = ["cand_H", "cand_H_peak", "H", "peak"]
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        last = None
        for row in r:
            last = row
        if last:
            for name in cand_names:
                if name in last and last[name] not in (None, ""):
                    try:
                        val = float(last[name])
                        print(f"[RUNNER] found CSV H in column '{name}': {val}", flush=True)
                        return val
                    except ValueError:
                        pass
    print("[RUNNER] CSV H not found", flush=True)
    return None


def main():
    print("[RUNNER] main() enter", flush=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, default="SUI")
    ap.add_argument("--limit-days", type=int, default=180)
    ap.add_argument("--seed-h", type=float, default=None,
                    help="Phase1에서 확정된 H를 직접 주입")
    ap.add_argument("--phase1-csv", type=str, default=None,
                    help="Phase1 CSV 경로 (cand_H/H/peak 컬럼)")
    ap.add_argument("--auto-phase1", action="store_true",
                    help="내장 Phase1 로직으로 H 자동 탐지")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    ensure_output_dir()
    print(f"[RUNNER] args: symbol={symbol}, limit_days={args.limit_days}, "
          f"seed_h={args.seed_h}, phase1_csv={args.phase1_csv}, auto={args.auto_phase1}", flush=True)

    try:
        print(f"[PH1.5] Fetch {symbol}USDT 1d OHLC (5y)…", flush=True)
        ohlc = get_binance_1d_ohlc_5y(f"{symbol}USDT")
        print(f"[RUNNER] OHLC rows: {len(ohlc)}", flush=True)

        # H 결정
        H: Optional[float] = None
        if args.seed_h:
            H = float(args.seed_h)
            print(f"[PH1.5] Use seeded H: {H}", flush=True)
        elif args.phase1_csv:
            H = load_H_from_csv(pathlib.Path(args.phase1_csv))
            if H is None:
                raise RuntimeError("Failed to read H from Phase1 CSV")
            print(f"[PH1.5] Use CSV H: {H}", flush=True)
        elif args.auto_phase1:
            highs = [row["high"] for row in ohlc]
            lows = [row["low"] for row in ohlc]
            H = compute_phase1_peak_signal_H(highs, lows)
            if H is None:
                raise RuntimeError("No Phase1 peak-signal H found")
            print(f"[PH1.5] Auto Phase1 H: {H}", flush=True)
        else:
            print("--seed-h 또는 --phase1-csv 또는 --auto-phase1 중 하나 필요", flush=True)
            sys.exit(1)

        # 실행
        out_csv = pathlib.Path("./output") / f"{symbol.lower()}_phase1_5_shadow.csv"
        print(f"[RUNNER] run simulation → {out_csv}", flush=True)
        run_phase1_5_simulation(symbol=symbol, ohlc=ohlc,
                                seed_H=H, out_csv=out_csv,
                                limit_days=args.limit_days)
        print(f"[OK] CSV saved: {out_csv}", flush=True)

    except Exception as e:
        print("[RUNNER][ERROR]", e, flush=True)
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    print("[RUNNER] __main__ guard", flush=True)
    main()
