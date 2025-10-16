#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_phase1_5.py — 개별 종목 디버그 CSV 생성 러너 (H 소스 선택 가능)

사용 예:
# 권장: OHLC에서 사이클 규칙으로 H 산출
python -u run_phase1_5.py --symbol SUIUSDT --limit-days 180

# 과거 디버그 CSV를 H 소스로
python -u run_phase1_5.py --symbol SUIUSDT --limit-days 180 --h-source csv --phase1-csv .\output\shadow\SUIUSDT_phase1_5_shadow_YYYYMMDD_HHMMSS.csv
"""

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional

# 1.5 코어 의존 모듈
try:
    from core.phase1_5_core import run_phase1_5_simulation, get_binance_1d_ohlc_5y
except Exception as e:
    print("[ERROR] import failed (core.phase1_5_core):", e)
    raise


# ---------------------------
# 날짜/형식 유틸
# ---------------------------

def _yyyymmdd_from_ms(ms: int) -> str:
    return dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _normalize_csv_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    if s.isdigit() and len(s) >= 10:
        ts = int(s[:10])
        return dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    return ""


def _pick_date_column(keys) -> str:
    cands = ["date", "Date", "close_time", "closeTime", "time", "Time"]
    for k in cands:
        if k in keys:
            return k
    return ""


# ---------------------------
# H 소스 ①: 과거 디버그 CSV에서 읽기
# ---------------------------

def load_daily_H_map_from_csv(csv_path: Path) -> Dict[str, float]:
    """
    과거 디버그 CSV에서 날짜별 H 매핑 생성.
    H 컬럼 후보: H, H_now, H_prev, daily_H
    동일 날짜가 여러 번 있으면 '뒤쪽(나중)' 값 우선.
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        raise FileNotFoundError(f"CSV not found or empty: {csv_path}")
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError("CSV empty")

    date_col = _pick_date_column(rows[0].keys())
    if not date_col:
        raise RuntimeError("CSV has no recognizable date column")

    H_cols = [c for c in ["H", "H_now", "H_prev", "daily_H"] if c in rows[0]]
    if not H_cols:
        raise RuntimeError("CSV has no H-like column (H/H_now/H_prev/daily_H)")
    h_col = H_cols[0]

    m: Dict[str, float] = {}
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
    return m


# ---------------------------
# H 소스 ②: OHLC에서 사이클 규칙으로 산출
# ---------------------------

def derive_daily_H_from_ohlc(ohlc_rows: List[dict]) -> Dict[str, float]:
    """
    Phase 1.5 사이클 규칙으로 날짜별 H 산출:
      - wait → high (저점 대비 +98.5%) 발생 시, H = 그날 high (리셋)
      - high 모드에서는 오늘 high > H 이면 H 갱신
      - wait 모드에서는 H 유지
      - high → wait 전환 조건: (low/H - 1) * 100 ≤ -44
    반환: { 'YYYY-MM-DD': H }
    """
    it = sorted(ohlc_rows, key=lambda r: int(r["closeTime"]))
    if not it:
        return {}

    # 초기값
    first = it[0]
    H = float(first["high"])
    L = float(first["low"])
    mode = "wait"

    daily_H: Dict[str, float] = {}

    for r in it:
        d = _yyyymmdd_from_ms(int(r["closeTime"]))
        high = float(r["high"])
        low = float(r["low"])

        # 상승/하락 퍼센트
        up_pct = ((high - L) / L * 100.0) if L else 0.0
        down_pct = ((low - H) / H * 100.0) if H else 0.0

        if mode == "wait":
            # 저점(L) 대비 +98.5% 반등 → high 모드 진입 & H 리셋
            if up_pct >= 98.5:
                mode = "high"
                H = high   # 리셋
                L = low    # 새 저점 기록
        else:
            # high 모드: 고점 갱신
            if high > H:
                H = high
            # -44% 하락 시 wait 전환
            if down_pct <= -44.0:
                mode = "wait"

        daily_H[d] = H

    return daily_H


# ---------------------------
# 메인 러너
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, required=True, help="예: SUIUSDT")
    ap.add_argument("--limit-days", type=int, default=180, help="최대 N일치 출력(코어에 전달)")
    ap.add_argument("--h-source", choices=["derive", "csv"], default="derive",
                    help="H 소스: derive(OHLC에서 산출, 기본) | csv(기존 디버그 CSV에서 읽기)")
    ap.add_argument("--phase1-csv", type=str, default="", help="--h-source csv 일 때 사용할 기존 디버그 CSV 경로")
    ap.add_argument("--out", type=str, default="", help="결과 디버그 CSV 출력 경로(미지정 시 자동명)")
    args = ap.parse_args()

    symbol = args.symbol.upper()

    # 1) OHLC 로드 (5년, 내부 코어 제공 함수 사용)
    ohlc = get_binance_1d_ohlc_5y(symbol)
    if not ohlc:
        raise RuntimeError(f"No OHLC rows for {symbol}")

    # 2) H 소스 준비
    if args.h_source == "csv":
        src = Path(args.phase1_csv)
        daily_H = load_daily_H_map_from_csv(src)
        print(f"[H-SOURCE=CSV] {src}  days={len(daily_H)}")
    else:
        daily_H = derive_daily_H_from_ohlc(ohlc)
        print(f"[H-SOURCE=DERIVE] days={len(daily_H)}")

    # 3) 엄격 검증: 모든 OHLC 날짜가 daily_H에 있어야 함
    missing = []
    for r in ohlc:
        d = _yyyymmdd_from_ms(int(r["closeTime"]))
        if d not in daily_H:
            missing.append(d)
    if missing:
        raise RuntimeError(f"daily_H missing {len(missing)} dates; e.g. {missing[:3]}")

    # 4) 출력 경로 결정
    if args.out:
        out_csv = Path(args.out)
    else:
        out_dir = Path("./output/shadow"); out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / f"{symbol}_phase1_5_shadow_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"

    # 5) 코어 호출
    seed_H = float(ohlc[0]["high"])
    run_phase1_5_simulation(
        symbol=symbol,
        ohlc=ohlc,
        seed_H=seed_H,
        out_csv=out_csv,
        limit_days=int(args.limit_days),
        daily_H=daily_H,  # ← 날짜별 H 주입 (핵심)
    )

    print("Saved:", out_csv)


if __name__ == "__main__":
    main()
