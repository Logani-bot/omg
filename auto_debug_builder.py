from __future__ import annotations
import os
import pathlib
from typing import Optional

import pandas as pd

from config.adapters import BinanceClient
from universe_selector import get_top30_coins, get_top30_symbols
from core.phase1_5_core import run_phase1_5_simulation


OUTPUT_DIR = pathlib.Path("data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_all(limit_days: int = 1200, symbols: Optional[list[str]] = None) -> list[str]:
    """
    Build per-symbol debug CSVs for Top100 (or provided symbols).
    - Downloads 일봉 OHLCV from Binance.
    - Computes Phase 1.5 debug table (H 루프 보정/리셋 포함).
    - Saves to data/{SYMBOL}_debug.csv
    - Excludes stablecoins, wrapped tokens, and unsupported symbols.
    Returns list of produced file paths (as str).
    """
    client = BinanceClient()
    syms = symbols or get_top30_symbols()
    
    # Binance API 미지원 심볼 제외 (스테이블코인, 래핑 토큰, 데이터 없음)
    exclude_symbols = {
        "USDTUSDT", "USDCUSDT", "USDEUSDT", "USDSUSDT", "DAIUSDT",  # 스테이블코인
        "WBTCUSDT", "WBETHUSDT", "WEETHUSDT", "STETHUSDT", "WSTETHUSDT",  # 래핑 토큰
        "FIGR_HELOCUSDT", "HYPEUSDT", "LEOUSDT", "USDT0USDT", "SUSDEUSDT",  # API 에러
        "MUSDT", "OKBUSDT", "WLFIUSDT", "BGBUSDT", "MNTUSDT", "CROUSDT"  # 데이터 없음
    }
    syms = [s for s in syms if s not in exclude_symbols]

    produced: list[str] = []
    for sym in syms:
        print(f"Processing {sym}...")
        try:
            df = client.get_ohlc_daily(sym, limit=limit_days)
            if df.empty:
                print(f"  {sym}: No data")
                continue
            
            # Convert DataFrame to list of dictionaries for run_phase1_5_simulation
            ohlc_data = []
            for _, row in df.iterrows():
                # Convert date to timestamp in milliseconds
                timestamp_ms = int(row['date'].timestamp() * 1000)
                
                # 2025-10-09 날짜의 저가 데이터를 종가로 대체 (이상 데이터 보정)
                date_str = row['date'].strftime('%Y-%m-%d')
                low_value = float(row['close']) if date_str == '2025-10-09' else float(row['low'])
                
                ohlc_data.append({
                    'closeTime': timestamp_ms,  # Use closeTime as expected by run_phase1_5_simulation
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': low_value,
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            
            # Remove USDT suffix for filename
            sym_name = sym.replace("USDT", "")
            out_path = OUTPUT_DIR / f"{sym_name}_debug.csv"
            
            run_phase1_5_simulation(
                symbol=sym,
                ohlc=ohlc_data,
                seed_H=None,  # H는 첫 사이클 시작 시 자동 설정
                out_csv=out_path,
                limit_days=limit_days
            )
            produced.append(str(out_path))
            print(f"  OK {sym} completed")
        except Exception as e:
            print(f"  SKIP {sym} - Error: {str(e)}")
            continue
    return produced


if __name__ == "__main__":
    files = build_all(limit_days=1200)
    print("[OK] generated:")
    for f in files:
        print(f" - {f}")
