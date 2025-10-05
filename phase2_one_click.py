#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2.0 — 원클릭 요약 (최종)
- Phase 1(top30) + Phase 1.5(core) 오케스트레이션
- 결과물:
  1) 당일 요약 CSV (시가총액 내림차순 정렬)
  2) 통합 Shadow 엑셀 (코인별 시트)
- 개별 shadow CSV는 출력하지 않음(사용자 혼동 방지).
  ※ 1.5 히스토리 연속성 유지를 위해 내부 상태 파일은 ./state/shadow/*.csv 로 유지(코어가 읽고 이어쓰기용).
"""

import argparse
import concurrent.futures as futures
import datetime as dt
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
import io

import pandas as pd

# --- 기존 모듈 재사용 ---
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
    return dt.datetime.now().strftime("%Y%m%d")

def _safe_sheet_name(base: str, used: set) -> str:
    """엑셀 시트명 제한(31자) 및 중복 방지."""
    name = (base or "SHEET")[:31]
    if name not in used:
        used.add(name); return name
    for i in range(2, 1000):
        cand = f"{name[:31-len(str(i))-1]}_{i}"
        if cand not in used:
            used.add(cand); return cand
    import hashlib
    h = hashlib.md5((base or "SHEET").encode()).hexdigest()[:6]
    cand = (base[:24] + "_" + h)[:31]
    used.add(cand); return cand

# ---------------------------------------
# 심볼 단위 분석 (Phase 1.5 실행 + 요약/엑셀용 데이터 반환)
# ---------------------------------------
def analyze_symbol(binance_symbol: str, name: str, lookback_days: int, market_cap: Optional[float]) -> dict:
    """
    반환:
      {
        'snapshot': {...},                 # 요약행(시가총액 포함)
        'shadow_csv_text': 'date,open,...' # 엑셀 시트로 쓸 전체 CSV 텍스트
      }
    또는 에러:
      { 'error': '...', 'symbol': 'BTCUSDT', 'name': 'Bitcoin' }
    """
    try:
        # 1) OHLC (코어 기대 포맷)
        rows = get_binance_1d_ohlc_5y(binance_symbol)
        if not rows:
            raise ValueError(f"No OHLC rows for {binance_symbol}")

        # 2) seed_H: 1.5와 동일한 동작을 위해 "첫 캔들 high"로 부팅
        seed_H = float(rows[0]["high"])

        # 3) 내부 상태 shadow 파일 (영속, 개별 출력물로 노출 X)
        state_csv = Path(f"./state/shadow/{binance_symbol}_phase1_5_shadow.csv")
        state_csv.parent.mkdir(parents=True, exist_ok=True)
        if not state_csv.exists():
            state_csv.touch()  # 코어가 read_text()할 때 비어 있어도 안전

        # 4) Phase 1.5 실행(코어가 state_csv를 읽고 이어쓰기)
        run_phase1_5_simulation(
            symbol=binance_symbol,
            ohlc=rows,
            seed_H=seed_H,
            out_csv=state_csv,           # 반드시 Path
            limit_days=lookback_days,
            daily_H=None,
        )

        # 5) 최신 shadow 텍스트 확보(엑셀 시트로 사용)
        shadow_text = state_csv.read_text(encoding="utf-8")
        lines = shadow_text.splitlines()

        # 6) 마지막 데이터 행 파싱 → 스냅샷 생성
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

        last_price      = g("close")
        mode            = g("mode", cast=str)
        stage           = g("stage", cast=lambda x: int(x) if x not in ("", "None") else 0, default=0)
        next_buy_level  = g("next_buy_level_name", cast=str, default="-")
        next_buy_price  = g("next_buy_level_price")
        H               = g("H")
        L_now           = g("L_now")
        rebound_from_L  = g("rebound_from_L_pct")
        cutoff          = g("cutoff_price")

        pct_to_next = pct_to_next_abs = drawdown_from_H = None
        if last_price is not None and next_buy_price is not None:
            pct_to_next = (next_buy_price - last_price) / last_price * 100
            pct_to_next_abs = abs(pct_to_next)
        if last_price is not None and H not in (None, 0):
            drawdown_from_H = (last_price / H - 1) * 100

        snapshot = {
            "universe": "COIN",
            "symbol": binance_symbol,
            "name": name,
            "market_cap": market_cap,  # ← 정렬용
            "last_price": round(last_price, ROUND_PRICE) if last_price is not None else None,
            "mode": mode,
            "in_position": "Y" if (stage or 0) > 0 else "N",
            "stage": stage or 0,
            "next_buy_level": next_buy_level,
            "next_buy_price": round(next_buy_price, ROUND_PRICE) if next_buy_price is not None else None,
            "pct_to_next_buy": round(pct_to_next, ROUND_PCT) if pct_to_next is not None else None,
            "pct_to_next_buy_abs": round(pct_to_next_abs, ROUND_PCT) if pct_to_next_abs is not None else None,
            "H": round(H, ROUND_PRICE) if H is not None else None,
            "L_now": round(L_now, ROUND_PRICE) if L_now is not None else None,
            "drawdown_from_H_pct": round(drawdown_from_H, ROUND_PCT) if drawdown_from_H is not None else None,
            "rebound_from_L_pct": round(rebound_from_L, ROUND_PCT) if rebound_from_L is not None else None,
            "buy_allowed_today": None,
            "sell_restricted": None,
            "notes": ("cutoff" if cutoff is not None else None),
        }

        return {
            "snapshot": snapshot,
            "shadow_csv_text": shadow_text,  # 엑셀 작성용
        }

    except Exception as e:
        return {
            "error": str(e),
            "universe": "COIN",
            "symbol": binance_symbol,
            "name": name,
            "market_cap": market_cap,
        }

# ---------------------------------------
# 메인
# ---------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK)
    ap.add_argument("--out", type=str, default=None)         # 당일 스냅샷 CSV
    ap.add_argument("--excel-out", type=str, default=None)   # 통합 Shadow 엑셀 경로
    ap.add_argument("--max-workers", type=str, default="auto")
    args = ap.parse_args()

    date_tag = now_seoul_date_str()
    out_csv = Path(args.out or Path("./output") / f"coins_snapshot_{date_tag}.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    excel_out = Path(args.excel_out) if args.excel_out else Path("./output") / f"coins_shadow_{date_tag}.xlsx"

    # 1) Top30 (Phase 1)
    print("[1/4] Selecting Top30 via Phase 1 (exclusions enabled)...")
    df_top = get_top30_binance(n_source=80)   # columns: symbol,name,binance_symbol,market_cap
    print(df_top.head())

    # map for lookup
    cap_map: Dict[str, float] = {row.binance_symbol: float(row.market_cap) if pd.notna(row.market_cap) else None
                                 for row in df_top.itertuples(index=False)}
    name_map: Dict[str, str]   = {row.binance_symbol: row.name for row in df_top.itertuples(index=False)}

    # 2) 병렬 분석
    items = list(df_top.itertuples(index=False))
    max_workers = os.cpu_count() - 1 if args.max_workers == "auto" else int(args.max_workers)
    max_workers = max(1, max_workers)
    print(f"[2/4] Running Phase 1.5 (workers={max_workers})...")

    results: List[dict] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(
            analyze_symbol,
            row.binance_symbol,
            row.name,
            args.lookback_days,
            float(row.market_cap) if pd.notna(row.market_cap) else None
        ) for row in items]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    # 3) 스냅샷 생성 + 시총 내림차순 정렬
    print("[3/4] Building snapshot DataFrame (sort by market_cap desc)...")
    snapshots = [r["snapshot"] for r in results if "snapshot" in r]
    df_snap = pd.DataFrame(snapshots)
    df_err  = pd.DataFrame([{"symbol": r.get("symbol"), "error": r.get("error")} for r in results if "error" in r])

    if not df_snap.empty:
        # 시총 내림차순 정렬, 동률 시 심볼로 보조 정렬
        df_snap = df_snap.sort_values(["market_cap", "symbol"], ascending=[False, True], na_position="last")

    # 저장
    df_snap.to_csv(out_csv, index=False)
    print(f"[3.5/4] Saved snapshot → {out_csv}")

    # 4) 통합 Shadow 엑셀 (코인별 탭)
    print("[4/4] Writing unified shadow Excel (one workbook, tabs per coin)...")
    # 엔진 선택
    engine = None
    try:
        import xlsxwriter  # noqa
        engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl  # noqa
            engine = "openpyxl"
        except Exception:
            engine = None

    if engine is None:
        print("[WARN] No Excel engine found. Skipping Excel export.")
    else:
        used = set()
        with pd.ExcelWriter(excel_out, engine=engine) as writer:
            # 첫 시트에 스냅샷 요약도 함께 저장(편의)
            df_snap.to_excel(writer, sheet_name=_safe_sheet_name("SUMMARY", used), index=False)

            # 각 코인 shadow 텍스트 → DF → 개별 시트
            for r in results:
                if "shadow_csv_text" not in r or "snapshot" not in r:
                    continue
                symbol = r["snapshot"].get("symbol")
                sheet = _safe_sheet_name(symbol or "SHEET", used)
                try:
                    df_shadow = pd.read_csv(io.StringIO(r["shadow_csv_text"]))
                except Exception:
                    # CSV 파싱 실패 시 원문을 그대로 1열로라도 덤프
                    df_shadow = pd.DataFrame({"raw": r["shadow_csv_text"].splitlines()})
                df_shadow.to_excel(writer, sheet_name=sheet, index=False)

        print(f"Saved unified shadow Excel → {excel_out}")

    # 에러 요약
    if not df_err.empty:
        print(f"⚠️ Errors for {len(df_err)} symbols:")
        print(df_err.head())

def run():
    main()

if __name__ == "__main__":
    run()
