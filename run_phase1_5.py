#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_phase1_5.py — Phase 1.5 디버그 CSV 생성 러너 (외부 주입 무시, OHLC로 H 직접 산출)

사용:
python -u run_phase1_5.py --symbol SUIUSDT --limit-days 180
"""

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional

# 1.5 코어
try:
    from core.phase1_5_core import run_phase1_5_simulation, get_binance_1d_ohlc_5y
except Exception as e:
    print("[ERROR] import failed (core.phase1_5_core):", e)
    raise


# ---------------------------
# 날짜/유틸
# ---------------------------

def _yyyymmdd_from_ms(ms: int) -> str:
    return dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


# ---------------------------
# OHLC → 날짜별 H 산출(우리 규칙)
# ---------------------------

def derive_daily_H_from_ohlc(ohlc_rows: List[dict]) -> Dict[str, float]:
    """
    규칙:
      - wait → high 전환(저점 L 대비 +98.5% 반등) 시 H = 그날 high (리셋)
      - high 모드: 오늘 high > H 이면 H 갱신
      - high → wait 전환: (low/H - 1) * 100 ≤ -44.0
      - wait 모드에서는 H 유지(리셋/갱신 없음)
    반환: {'YYYY-MM-DD': H}
    """
    rows = sorted(ohlc_rows, key=lambda r: int(r["closeTime"]))
    if not rows:
        return {}

    H = float(rows[0]["high"])
    L = float(rows[0]["low"])
    mode = "wait"

    daily_H: Dict[str, float] = {}

    for r in rows:
        d = _yyyymmdd_from_ms(int(r["closeTime"]))
        hi = float(r["high"])
        lo = float(r["low"])

        up   = ((hi - L) / L * 100.0) if L else 0.0
        down = ((lo - H) / H * 100.0) if H else 0.0

        if mode == "wait":
            # 저점 대비 +98.5% 반등 → high 진입 & H 리셋
            if up >= 98.5:
                mode = "high"
                H = hi
                L = lo  # 새 저점 기록
        else:  # mode == "high"
            # 고점 갱신
            if hi > H:
                H = hi
            # -44% 하락 → wait 전환
            if down <= -44.0:
                mode = "wait"
                # L은 이후 자연 갱신(추가 로직 필요시 확장)

        daily_H[d] = H

    return daily_H


# ---------------------------
# 메인 러너
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, required=True, help="예: SUIUSDT")
    ap.add_argument("--limit-days", type=int, default=180, help="코어 최종 출력 일수 제한")
    ap.add_argument("--out", type=str, default="", help="결과 디버그 CSV 경로(미지정 시 자동명)")
    args = ap.parse_args()

    symbol = args.symbol.upper()

    # 1) OHLC 로드 (5년)
    ohlc = get_binance_1d_ohlc_5y(symbol)
    if not ohlc:
        raise RuntimeError(f"No OHLC rows for {symbol}")

    # 2) 날짜별 H 직접 산출
    daily_H = derive_daily_H_from_ohlc(ohlc)
    if not daily_H:
        raise RuntimeError("daily_H derive failed (no rows)")

    # 3) 엄격 검증: 모든 OHLC 날짜가 daily_H에 있어야 함
    missing = []
    for r in ohlc:
        d = _yyyymmdd_from_ms(int(r["closeTime"]))
        if d not in daily_H:
            missing.append(d)
    if missing:
        raise RuntimeError(f"daily_H missing {len(missing)} dates; e.g. {missing[:3]}")

    # 4) seed_H = 첫 날짜의 daily_H
    first_date = _yyyymmdd_from_ms(int(ohlc[0]["closeTime"]))
    seed_H = float(daily_H[first_date])

    # 5) 출력 경로
    if args.out:
        out_csv = Path(args.out)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path("./output/shadow")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / f"{symbol}_phase1_5_shadow_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"

    # 6) 코어 호출 (daily_H 강제 주입)
    run_phase1_5_simulation(
        symbol=symbol,
        ohlc=ohlc,
        seed_H=seed_H,
        out_csv=out_csv,
        limit_days=int(args.limit_days),
        daily_H=daily_H,
    )

    print("Saved:", out_csv)


if __name__ == "__main__":
    main()
