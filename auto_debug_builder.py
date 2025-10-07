from __future__ import annotations
import os
import pathlib
from typing import Optional

import pandas as pd

from config.adapters import BinanceClient
from top30 import get_top30_symbols
from phase1_5_core import compute_omg_debug


OUTPUT_DIR = pathlib.Path("state/shadow")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_all(limit_days: int = 1200, symbols: Optional[list[str]] = None) -> list[str]:
    """
    Build per-symbol debug CSVs for Top30 (or provided symbols).
    - Downloads 일봉 OHLCV from Binance.
    - Computes Phase 1.5 debug table (H 루프 보정/리셋 포함).
    - Saves to state/shadow/{SYMBOL}_debug.csv
    Returns list of produced file paths (as str).
    """
    client = BinanceClient()
    syms = symbols or get_top30_symbols()

    produced: list[str] = []
    for sym in syms:
        df = client.get_ohlc_daily(sym, limit=limit_days)
        if df.empty:
            continue
        dbg = compute_omg_debug(df)
        out_path = OUTPUT_DIR / f"{sym}_debug.csv"
        dbg.to_csv(out_path, index=False)
        produced.append(str(out_path))
    return produced


if __name__ == "__main__":
    files = build_all(limit_days=1200)
    print("[OK] generated:")
    for f in files:
        print(f" - {f}")
