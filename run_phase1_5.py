#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Runner — debug CSV의 H를 '모든 날짜'에 대해 매칭
- 규칙:
  * OHLC 전체(5년)를 사용
  * debug CSV에서 날짜별 'H'를 읽어 (YYYY-MM-DD → H) 매핑 생성
  * OHLC의 모든 날짜가 CSV에 존재해야 함(엄격). 없으면 에러 종료
  * 코어는 각 일자마다 전달된 H로 레벨(B1~B7)을 재계산 후, 저가 매수/고가 매도 로직 수행
- 출력 CSV는 타임스탬프를 붙여 파일 잠금 충돌 방지
"""

import argparse
import csv
import pathlib
import sys
import traceback
from datetime import datetime
from typing import Dict, Optional, Iterable

print("[RUNNER] module import start", flush=True)

from core.phase1_5_core import (
    get_binance_1d_ohlc_5y,
    run_phase1_5_simulation,
)

print("[RUNNER] core imported OK", flush=True)


def _yyyymmdd_from_ms(ms: int) -> str:
    return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _pick_date_column(headers: Iterable[str]) -> Optional[str]:
    candidates = ["date", "Date", "DATE", "timestamp", "Timestamp", "TIME", "time"]
    for c in candidates:
        if c in headers:
            return c
    return None


def _normalize_csv_date(s: str) -> Optional[str]:
    if not s:
        return None
    t = s.strip()
    t = t.split(" ")[0]
    t = t.replace(".", "-").replace("/", "-")
    try:
        d = datetime.strptime(t, "%Y-%m-%d")
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


def load_daily_H_map(csv_path: pathlib.Path, h_col: str = "H") -> Dict[str, float]:
    """
    debug CSV에서 날짜별 H 매핑(YYYY-MM-DD -> float)을 만든다.
    동일 날짜가 여러 번 나오면 '아래쪽(뒤쪽)' 값을 우선한다(가장 나중 기록).
    """
    print(f"[RUNNER] load_daily_H_map: {csv_path} (col={h_col})", flush=True)
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError("CSV empty")
    if h_col not in rows[0]:
        raise RuntimeError(f"CSV missing '{h_col}' column")

    date_col = _pick_date_column(rows[0].keys())
    if not date_col:
        raise RuntimeError("CSV has no recognizable date column")

    m: Dict[str, float] = {}
    # 아래에서 위로 스캔(뒤쪽이 우선)
    for row in reversed(rows):
        d = _normalize_csv_date(str(row.get(date_col, "")))
        if not d:
            continue
        raw = row.get(h_col, "")
        if raw is None:
            continue
        s = str(raw).strip().replace(",", "")
        if s == "" or s.lower() in ("nan", "none"):
            continue
        try:
            val = float(s)
        except ValueError:
            continue
        # 동일 날짜는 '가장 뒤쪽' 값이 최종
        if d not in m:
            m[d] = val
    print(f"[RUNNER] daily H loaded: {len(m)} dates", flush=True)
    return m


def main():
    print("[RUNNER] main() enter", flush=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, default="SUI")
    ap.add_argument("--limit-days", type=int, default=180)
    ap.add_argument("--phase1-csv", type=str, required=True,
                    help="Phase 1 debug CSV 경로 (반드시 날짜별 'H' 컬럼 포함)")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    pathlib.Path("./output").mkdir(parents=True, exist_ok=True)
    print(f"[RUNNER] args: symbol={symbol}, limit_days={args.limit_days}, phase1_csv={args.phase1_csv}", flush=True)

    try:
        # 0) 데이터 로드 (일봉 5년)
        print(f"[PH1.5] Fetch {symbol}USDT 1d OHLC (5y)…", flush=True)
        ohlc = get_binance_1d_ohlc_5y(f"{symbol}USDT")
        print(f"[RUNNER] OHLC rows: {len(ohlc)}", flush=True)
        if not ohlc:
            print("[RUNNER][ERROR] No OHLC data", flush=True)
            sys.exit(1)

        # 1) 날짜별 H 매핑 로드
        csv_path = pathlib.Path(args.phase1_csv)
        if not csv_path.exists():
            print(f"[RUNNER][ERROR] CSV not found: {csv_path}", flush=True)
            sys.exit(1)
        daily_H = load_daily_H_map(csv_path, h_col="H")

        # 2) 엄격 검증: OHLC 모든 날짜가 CSV에 존재해야 함
        missing = []
        for r in ohlc:
            d = _yyyymmdd_from_ms(r["closeTime"])
            if d not in daily_H:
                missing.append(d)
        if missing:
            print("[RUNNER][ERROR] H missing for some dates in debug CSV (strict mode).", flush=True)
            print(" Missing sample (up to 10):", ", ".join(missing[:10]), flush=True)
            print(" Please ensure the debug CSV has 'H' for every OHLC date.", flush=True)
            sys.exit(1)

        # 3) 출력 파일명(타임스탬프)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = pathlib.Path("./output") / f"{symbol.lower()}_phase1_5_shadow_{stamp}.csv"
        print(f"[RUNNER] run simulation → {out_csv}", flush=True)

        # 4) 시뮬레이션 실행 (날짜별 H 매핑 전달)
        run_phase1_5_simulation(
            symbol=symbol,
            ohlc=ohlc,
            seed_H=None,                 # seed는 사용하지 않음
            out_csv=out_csv,
            limit_days=args.limit_days,
            daily_H=daily_H              # 날짜별 H 맵 전달
        )
        print(f"[OK] CSV saved: {out_csv}", flush=True)

    except Exception as e:
        print("[RUNNER][ERROR]", e, flush=True)
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    print("[RUNNER] __main__ guard", flush=True)
    main()
