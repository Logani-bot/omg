#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 — ONE CLICK (FINAL, CORE 통합)
입력: ./data/<symbol>_debug.csv (omg2.py 산출) 또는 CORE로 새로 생성한 shadow
결과: ./data 폴더 (snapshot CSV + Excel + p1.5 trades/summary)
"""

import os
import sys
import pandas as pd
import datetime as dt
from pathlib import Path
from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------
# import core / run dynamically
# ---------------------------------------------------------------------
try:
    sys.path.append(str(Path(__file__).resolve().parent))
    sys.path.append(str(Path(__file__).resolve().parent / "core"))
    from core.phase1_5_core import run_phase1_5_simulation, get_binance_1d_ohlc_5y as derive_daily_H_from_ohlc
    from run_phase1_5 import get_binance_1d_ohlc_5y
except Exception as e:
    print(f"[WARN] core/phase1_5_core or run_phase1_5 import failed: {e}")
    derive_daily_H_from_ohlc = None
    run_phase1_5_simulation = None
    get_binance_1d_ohlc_5y = None

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
OUTPUT_DIR = Path("./data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

P15_TRADES_DIR = OUTPUT_DIR / "phase1p5_trades"
P15_TRADES_DIR.mkdir(parents=True, exist_ok=True)
P15_CORE_DEBUG_DIR = OUTPUT_DIR / "phase1_5_core"
P15_CORE_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
P15_SUMMARY_CSV = OUTPUT_DIR / "phase1p5_summary.csv"

DEFAULT_OUT_CSV = OUTPUT_DIR / f"phase2_snapshot_{dt.datetime.now().strftime('%Y%m%d')}.csv"
DEFAULT_XLSX_OUT = OUTPUT_DIR / f"phase2_shadow_{dt.datetime.now().strftime('%Y%m%d')}.xlsx"

# ---------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------
def read_debug_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return pd.read_csv(path)

def snapshot_from_debug(symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Generate summary snapshot from debug dataframe."""
    if df.empty:
        return {"symbol": symbol, "status": "no data"}
    last = df.iloc[-1]
    return {
        "symbol": symbol,
        "last_date": last.get("date"),
        "last_mode": last.get("mode"),
        "H": last.get("H"),
        "L": last.get("L"),
        "close": last.get("close"),
    }

# ---------------------------------------------------------------------
# Phase 1.5 core shadow generator
# ---------------------------------------------------------------------
def _ensure_core_shadow(symbol: str) -> Path:
    """core 백엔드일 때: 심볼 shadow CSV + (가능하면) core 트레이드까지 생성."""
    if run_phase1_5_simulation is None or get_binance_1d_ohlc_5y is None or derive_daily_H_from_ohlc is None:
        raise RuntimeError("Phase1.5 core imports unavailable; set --p15-backend inline or off")

    pair = f"{symbol.upper()}USDT"
    print(f"[CORE] Fetching {pair} 1d OHLC …")
    ohlc = get_binance_1d_ohlc_5y(pair)
    if not ohlc:
        raise RuntimeError(f"No OHLC rows for {pair}")

    daily_H = derive_daily_H_from_ohlc(ohlc)
    seed_H = float(ohlc[0]["high"])
    core_df_path = P15_CORE_DEBUG_DIR / f"{symbol.lower()}_phase1_5_shadow.csv"
    core_trade_csv = P15_TRADES_DIR / f"{symbol.lower()}_trades_core.csv"
    core_summary_csv = P15_SUMMARY_CSV

    print(f"[CORE] Running phase1_5_core simulation for {symbol} …")
    run_phase1_5_simulation(
        symbol=symbol.upper(),
        ohlc=ohlc,
        seed_H=seed_H,
        out_csv=core_df_path,
        limit_days=2000,
        daily_H=daily_H,
        trades_csv=str(core_trade_csv),
        summary_csv=str(core_summary_csv),
    )
    print(f"[CORE] Saved {core_df_path}")
    return core_df_path

# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-dir", type=str, default="./data")
    parser.add_argument("--universe-file", type=str, default=None)
    parser.add_argument("--universe-col", type=str, default="symbol")
    parser.add_argument("--p15-backend", type=str, default="core", choices=["core", "inline", "off"])
    parser.add_argument("--limit-days", type=int, default=2000)
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--excel-out", type=str, default=str(DEFAULT_XLSX_OUT))
    args = parser.parse_args()

    debug_dir = Path(args.debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)

    # load universe
    if args.universe_file:
        dfu = pd.read_csv(args.universe_file)
        symbols = dfu[args.universe_col].dropna().unique().tolist()
    else:
        symbols = sorted([f.stem.replace("_debug", "").upper() for f in debug_dir.glob("*_debug.csv")])

    if not symbols:
        raise RuntimeError("No symbols found in debug dir or universe file")

    snapshots = []
    excel_out = Path(args.excel_out)
    engine = "xlsxwriter" if "xlsxwriter" in sys.modules or True else None

    with pd.ExcelWriter(excel_out, engine=engine) as writer:
        for i, symbol in enumerate(symbols, 1):
            try:
                if args.p15_backend == "core":
                    csv_path = _ensure_core_shadow(symbol)
                    df = read_debug_csv(csv_path)
                else:
                    csv_path = debug_dir / f"{symbol.lower()}_debug.csv"
                    df = read_debug_csv(csv_path)

                snap = snapshot_from_debug(symbol, df)
                snapshots.append(snap)
                df.to_excel(writer, index=False, sheet_name=symbol[:31])

                # core trade sheet
                core_trade_csv = P15_TRADES_DIR / f"{symbol.lower()}_trades_core.csv"
                if core_trade_csv.exists():
                    tdf = pd.read_csv(core_trade_csv)
                    if not tdf.empty:
                        tdf.to_excel(writer, index=False, sheet_name=f"TRADES_{symbol}"[:31])

                print(f"[RUN] {i}/{len(symbols)} {symbol} → OK")
            except Exception as e:
                print(f"[SKIP] {symbol}: {e}")

        pd.DataFrame(snapshots).to_excel(writer, index=False, sheet_name="SUMMARY")
        print(f"[DONE] Excel saved → {excel_out}")

    pd.DataFrame(snapshots).to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"[DONE] Snapshot saved → {args.out}")

if __name__ == "__main__":
    main()
