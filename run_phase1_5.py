#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Runner — Phase 1 기반
- H(Phase 1 고점 신호) 결정 우선순위:
  1) --phase1-csv 에서 as-of 날짜(있다면) 기준으로 'H' 컬럼을 읽음
  2) --seed-h 사용
  3) (예외 부트스트랩) 시작일의 고가(high)를 H로 채택
- 시뮬레이션 규칙(코어에 구현):
  * 매수: 저가 기준 (레벨 터치)
  * 매도: 고가 기준 (L 대비 단계별 반등률)
- 출력 CSV는 타임스탬프를 붙여 파일 잠금 충돌을 방지
"""

import argparse
import csv
import pathlib
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional

print("[RUNNER] module import start", flush=True)

from core.phase1_5_core import (
    get_binance_1d_ohlc_5y,
    run_phase1_5_simulation,
)

print("[RUNNER] core imported OK", flush=True)


def load_H_from_csv(csv_path: pathlib.Path,
                    h_col: str = "H",
                    asof: Optional[str] = None,
                    date_col_candidates=("date", "Date", "DATE")) -> Optional[float]:
    """
    Phase 1 CSV에서 최종 H를 읽어온다.
    - cand_H는 무시. 반드시 h_col('H')만 사용.
    - asof(YYYY-MM-DD)가 주어지면, 그 날짜 '이전/같은' 행 중 가장 최근 H를 선택.
    """
    print(f"[RUNNER] load_H_from_csv: {csv_path} (col={h_col}, asof={asof})", flush=True)
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("[RUNNER] CSV empty", flush=True)
        return None
    if h_col not in rows[0]:
        print(f"[RUNNER] missing column '{h_col}'", flush=True)
        return None

    asof_dt = None
    if asof:
        asof_dt = datetime.strptime(asof, "%Y-%m-%d").date()

    def row_date_ok(row):
        if asof_dt is None:
            return True
        for dc in date_col_candidates:
            if dc in row and row[dc]:
                try:
                    d = row[dc].split(" ")[0]
                    rd = datetime.strptime(d, "%Y-%m-%d").date()
                    return rd <= asof_dt
                except Exception:
                    continue
        # 날짜 컬럼을 못 찾으면 보수적으로 허용
        return True

    # 아래에서 위로(최신 행부터) 스캔
    for row in reversed(rows):
        if not row_date_ok(row):
            continue
        raw = row.get(h_col, "")
        if raw is None:
            continue
        s = str(raw).strip().replace(",", "")
        if s == "" or s.lower() in ("nan", "none"):
            continue
        try:
            val = float(s)
            print(f"[RUNNER] H found: column='{h_col}', value={val}", flush=True)
            return val
        except ValueError:
            continue

    print(f"[RUNNER] H not found (col='{h_col}', asof={asof})", flush=True)
    return None


def main():
    print("[RUNNER] main() enter", flush=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, default="SUI")
    ap.add_argument("--limit-days", type=int, default=180)
    ap.add_argument("--phase1-csv", type=str, default=None, help="Phase 1 산출 CSV 경로(헤더에 'H' 컬럼 필수)")
    ap.add_argument("--seed-h", type=float, default=None, help="Phase 1에서 확정된 H를 직접 주입")
    ap.add_argument("--asof", type=str, default=None, help="H를 이 날짜(YYYY-MM-DD) 기준으로 선택")
    ap.add_argument("--start-date", type=str, default=None, help="이 날짜(YYYY-MM-DD)부터 시뮬레이션")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    pathlib.Path("./output").mkdir(parents=True, exist_ok=True)
    print(f"[RUNNER] args: symbol={symbol}, limit_days={args.limit_days}, "
          f"phase1_csv={args.phase1_csv}, seed_h={args.seed_h}, asof={args.asof}, start_date={args.start_date}", flush=True)

    try:
        # 0) 데이터 로드 (일봉 5년)
        print(f"[PH1.5] Fetch {symbol}USDT 1d OHLC (5y)…", flush=True)
        ohlc = get_binance_1d_ohlc_5y(f"{symbol}USDT")
        print(f"[RUNNER] OHLC rows: {len(ohlc)}", flush=True)
        if not ohlc:
            print("[RUNNER][ERROR] No OHLC data", flush=True)
            sys.exit(1)

        # 0-1) 시작일 슬라이스 (원하면)
        if args.start_date:
            sd = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            sd_ms = int(sd.timestamp() * 1000)
            ohlc = [r for r in ohlc if r["closeTime"] >= sd_ms]
            print(f"[RUNNER] OHLC sliced from {args.start_date}: {len(ohlc)} rows", flush=True)
            if not ohlc:
                print("[RUNNER][ERROR] No OHLC rows after start-date slice", flush=True)
                sys.exit(1)

        # 1) H 결정 — CSV as-of → seed → (부트스트랩) 시작일 고가
        H: Optional[float] = None

        # (1) CSV 최우선 ('H' 컬럼만 사용)
        if args.phase1_csv:
            csv_path = pathlib.Path(args.phase1_csv)
            if not csv_path.exists():
                # 사용자가 .\output\.. 로 준 경우, 경로 정규화 로그만 출력
                print(f"[RUNNER][WARN] CSV not found at {csv_path}. Trying as given path string..", flush=True)
            H = load_H_from_csv(csv_path, h_col="H", asof=args.asof)
            if H is not None:
                print(f"[PH1.5] Use Phase1 CSV H (asof={args.asof}): {H}", flush=True)

        # (2) seed-h
        if H is None and args.seed_h is not None:
            H = float(args.seed_h)
            print(f"[PH1.5] Use seeded H: {H}", flush=True)

        # (3) (예외 부트스트랩) 시작일의 고가(high)를 H로 채택
        if H is None:
            first_high = ohlc[0]["high"]
            H = float(first_high)
            print(f"[PH1.5][BOOTSTRAP] No prior H. Bootstrap H with first-day high: {H}", flush=True)

        # 2) 출력 파일명(타임스탬프) — 파일 잠금 충돌 방지
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = pathlib.Path("./output") / f"{symbol.lower()}_phase1_5_shadow_{stamp}.csv"
        print(f"[RUNNER] run simulation → {out_csv}", flush=True)

        # 3) 시뮬레이션 실행
        run_phase1_5_simulation(
            symbol=symbol,
            ohlc=ohlc,
            seed_H=H,
            out_csv=out_csv,
            limit_days=args.limit_days
        )
        print(f"[OK] CSV saved: {out_csv}", flush=True)

    except Exception as e:
        print("[RUNNER][ERROR]", e, flush=True)
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    print("[RUNNER] __main__ guard", flush=True)
    main()
