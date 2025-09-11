#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Runner — debug CSV의 H를 '모든 날짜'에 대해 매칭 (엄격) + OHLC 자동 트림
- OHLC: 바이낸스 1d * 5년
- H: debug CSV에서 날짜별 'H'를 읽어 YYYY-MM-DD → H 매핑 생성
- OHLC의 날짜가 CSV 커버리지를 넘어가면, CSV의 마지막 날짜까지만 자동으로 잘라 사용
- 잘린 구간(공통 구간) 안에서 H가 빈 날짜가 있으면 에러로 종료
- 코어는 각 일자마다 해당 H로 레벨 재계산 후, 저가 매수 / 고가 매도 수행
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
        # 0) OHLC 로드
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

        # 2) 공통 구간 산출: CSV가 커버하는 마지막 날짜까지만 OHLC 사용
        h_dates = sorted(daily_H.keys())
        last_h_date = h_dates[-1]  # CSV가 커버하는 마지막 날짜
        full_len = len(ohlc)
        ohlc = [r for r in ohlc if _yyyymmdd_from_ms(r["closeTime"]) <= last_h_date]
        print(f"[RUNNER] OHLC trimmed to CSV last date {last_h_date}: {len(ohlc)} rows (from {full_len})", flush=True)
        if not ohlc:
            print("[RUNNER][ERROR] No OHLC rows after trim to CSV coverage", flush=True)
            sys.exit(1)

        # 3) 엄격 검증: 공통 구간 안의 모든 날짜에 H가 있어야 함
        missing = []
        for r in ohlc:
            d = _yyyymmdd_from_ms(r["closeTime"])
            if d not in daily_H:
                missing.append(d)
        if missing:
            print("[RUNNER][ERROR] H missing inside common date range (strict).", flush=True)
            print(" Missing sample (up to 10):", ", ".join(sorted(set(missing))[:10]), flush=True)
            print(" Please ensure the debug CSV has 'H' for every date in the used period.", flush=True)
            sys.exit(1)

        # 4) 출력 파일명
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = pathlib.Path("./output") / f"{symbol.lower()}_phase1_5_shadow_{stamp}.csv"
        print(f"[RUNNER] run simulation → {out_csv}", flush=True)

        # 5) 시뮬레이션 실행
        run_phase1_5_simulation(
            symbol=symbol,
            ohlc=ohlc,
            seed_H=None,                 # daily_H 모드이므로 seed는 사용하지 않음
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
