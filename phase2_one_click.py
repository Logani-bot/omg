#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2.0 — 원클릭 요약 (state/shadow 정비판)
- Phase 1(top30) + Phase 1.5(core)
- 변경 포인트:
  1) 코어 출력은 항상 "임시 디버그 CSV"로 먼저 생성 → 스키마/헤더/일자 검증 → state/shadow에 병합
  2) daily_H는 state/shadow에서 날짜별 맵으로 로드해 코어에 주입(1.5와 동일)
  3) 스냅샷/엑셀은 state/shadow 기준으로 생성 (임시 파일 무시)
"""

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import io
import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# --- 외부 모듈 재사용 ---
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

REQUIRED_COLS = [
    "date","open","high","low","close",
    "H","L_now","mode","stage","event",
    "next_buy_level_name","next_buy_level_price","cutoff_price"
]

def now_seoul_date_str() -> str:
    return dt.datetime.now().strftime("%Y%m%d")


# ---------- 날짜 유틸 ----------
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


# ---------- shadow 로더 (daily_H / last_row) ----------
def load_daily_H_map(csv_path: Path) -> Dict[str, float]:
    """state/shadow CSV에서 날짜별 H 매핑(뒤쪽 기록 우선). H 컬럼 후보 자동 감지."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return {}
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    date_col = _pick_date_column(rows[0].keys())
    if not date_col:
        return {}
    # H 후보 컬럼들
    H_cols = [c for c in ["H", "H_now", "H_prev", "daily_H"] if c in rows[0]]
    if not H_cols:
        return {}
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
    if m:
        print(f"[DAILY_H] {csv_path.name}: loaded {len(m)} days (col={h_col})")
    else:
        print(f"[DAILY_H] {csv_path.name}: no H found")
    return m


def _read_all(csv_path: Path) -> List[dict]:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_last_row(csv_path: Path) -> Optional[dict]:
    rows = _read_all(csv_path)
    return rows[-1] if rows else None


# ---------- 부팅: 과거 debug/shadow에서 시드 복사 ----------
def bootstrap_shadow_if_needed(symbol: str, state_csv: Path, bootstrap_dir: Optional[Path]) -> None:
    if state_csv.exists() and state_csv.stat().st_size > 0:
        return
    if not bootstrap_dir or not bootstrap_dir.exists():
        return
    sym_lower = symbol.lower()
    cands = []
    for p in bootstrap_dir.rglob("*_phase1_5_shadow*.csv"):
        if sym_lower in p.name.lower():
            cands.append(p)
    if not cands:
        print(f"[BOOT] no seed found for {symbol} under {bootstrap_dir}")
        return
    cands.sort(key=lambda p: p.stat().st_mtime)
    src = cands[-1]
    try:
        txt = src.read_text(encoding="utf-8")
        state_csv.parent.mkdir(parents=True, exist_ok=True)
        state_csv.write_text(txt, encoding="utf-8")
        print(f"[BOOT] seeded shadow from: {src} → {state_csv.name}")
    except Exception as e:
        print(f"[BOOT][WARN] seed failed for {symbol}: {e}")


# ---------- OHLC 증분 필터 ----------
def _ohlc_date_str_from_row(r: dict) -> str:
    return dt.datetime.utcfromtimestamp(int(r["closeTime"]) / 1000).strftime("%Y-%m-%d")


def filter_ohlc_increment(rows: List[dict], last_date: Optional[str]) -> List[dict]:
    if not last_date:
        return rows
    return [r for r in rows if _ohlc_date_str_from_row(r) > last_date]


# ---------- 시트명 유틸 ----------
def _safe_sheet_name(base: str, used: set) -> str:
    name = (base or "SHEET")[:31]
    if name not in used:
        used.add(name)
        return name
    for i in range(2, 1000):
        cand = f"{name[:31 - len(str(i)) - 1]}_{i}"
        if cand not in used:
            used.add(cand)
            return cand
    h = hashlib.md5((base or "SHEET").encode()).hexdigest()[:6]
    cand = (base[:24] + "_" + h)[:31]
    used.add(cand)
    return cand


# ---------- shadow 병합(핵심) ----------
def _normalize_header_order(cols: List[str]) -> List[str]:
    # REQUIRED_COLS 우선, 그 외는 뒤에 그대로
    ordered = []
    seen = set()
    for c in REQUIRED_COLS:
        if c in cols:
            ordered.append(c); seen.add(c)
    for c in cols:
        if c not in seen:
            ordered.append(c); seen.add(c)
    return ordered


def merge_shadow_csvs(base_path: Path, tmp_path: Path) -> None:
    """
    1) base(state)와 tmp(core 출력)를 읽어 날짜 키 기준 병합
    2) 헤더 정규화(REQUIRED_COLS 우선)
    3) 중복 날짜는 tmp 쪽(새로 계산된 값)을 우선
    """
    base_rows = _read_all(base_path)
    tmp_rows  = _read_all(tmp_path)

    if not tmp_rows:
        return  # 코어가 이번에 생성 안 했으면 건너뜀

    # date 컬럼 찾기
    def get_date_key(row: dict) -> str:
        for k in ["date","Date","close_time","closeTime","time","Time"]:
            if k in row and row[k]:
                return _normalize_csv_date(str(row[k]))
        return ""

    # 인덱스 만들기
    base_idx: Dict[str,int] = {}
    for i, r in enumerate(base_rows):
        d = get_date_key(r)
        if d:
            base_idx[d] = i

    # 병합
    for r in tmp_rows:
        d = get_date_key(r)
        if not d:
            continue
        if d in base_idx:
            base_rows[base_idx[d]] = r  # 새 값으로 교체
        else:
            base_rows.append(r)

    # 헤더 정규화
    all_cols = list(base_rows[0].keys()) if base_rows else list(tmp_rows[0].keys())
    cols = _normalize_header_order(all_cols)

    # 저장
    base_path.parent.mkdir(parents=True, exist_ok=True)
    with open(base_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(base_rows, key=lambda x: get_date_key(x)):
            w.writerow({c: r.get(c, "") for c in cols})


# ---------- 개별 심볼 분석 ----------
def analyze_symbol(
    binance_symbol: str,
    name: str,
    lookback_days: int,
    market_cap: Optional[float],
    bootstrap_dir: Optional[Path],
) -> dict:
    try:
        # 0) state 파일(영속)
        state_csv = Path(f"./state/shadow/{binance_symbol}_phase1_5_shadow.csv")
        state_csv.parent.mkdir(parents=True, exist_ok=True)

        # 1) 필요 시 부팅
        bootstrap_shadow_if_needed(binance_symbol, state_csv, bootstrap_dir)

        # 2) OHLC 전체 + 증분
        rows_all = get_binance_1d_ohlc_5y(binance_symbol)
        if not rows_all:
            raise ValueError(f"No OHLC rows for {binance_symbol}")
        last_row = _read_last_row(state_csv)
        last_date = None
        if last_row:
            for k in ["date","Date","close_time","closeTime","time","Time"]:
                if k in last_row and last_row[k]:
                    last_date = _normalize_csv_date(str(last_row[k])); break
        rows = filter_ohlc_increment(rows_all, last_date) if last_date else rows_all

        # 3) daily_H 주입(어제까지)
        daily_H_map = load_daily_H_map(state_csv)
        daily_H_arg = daily_H_map if daily_H_map else None

        # 4) 코어를 "임시 디버그 CSV"로 실행 (항상 새로 생성)
        tmp_dir = Path("./state/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_csv = tmp_dir / f"{binance_symbol}_shadow_run.csv"

        seed_H = float(rows_all[0]["high"])  # 최초만 의미
        if rows:  # 증분 있을 때만 코어 실행
            run_phase1_5_simulation(
                symbol=binance_symbol,
                ohlc=rows,
                seed_H=seed_H,
                out_csv=tmp_csv,
                limit_days=lookback_days,
                daily_H=daily_H_arg,
            )

        # 5) 임시 디버그 CSV를 state/shadow에 병합(스키마/헤더 포함)
        merge_shadow_csvs(state_csv, tmp_csv)
        if tmp_csv.exists():
            try:
                tmp_csv.unlink()
            except Exception:
                pass

        # 6) 최신 state에서 마지막 행 파싱
        last = _read_last_row(state_csv)
        if not last:
            raise ValueError("Shadow CSV still empty after merge")

        def gx(key, cast=float, default=None):
            v = last.get(key)
            if v in (None, "", "None"):
                return default
            try:
                return cast(v) if cast else v
            except Exception:
                return default

        last_price      = gx("close")
        mode            = gx("mode", cast=str)
        stage           = gx("stage", cast=lambda x: int(x) if x not in ("", "None") else 0, default=0)
        next_buy_level  = gx("next_buy_level_name", cast=str, default="-")
        next_buy_price  = gx("next_buy_level_price")
        H               = gx("H")
        L_now           = gx("L_now")
        rebound_from_L  = gx("rebound_from_L_pct")
        cutoff          = gx("cutoff_price")

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
            "market_cap": market_cap,
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
            "state_csv_path": str(state_csv),  # 엑셀 병합 시 직접 읽음
        }

    except Exception as e:
        return {
            "error": str(e),
            "universe": "COIN",
            "symbol": binance_symbol,
            "name": name,
            "market_cap": market_cap,
        }


# ---------- 메인 ----------
def main():
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK)
    ap.add_argument("--out", type=str, default=None)        # 스냅샷 CSV
    ap.add_argument("--excel-out", type=str, default=None)  # 통합 Shadow 엑셀
    ap.add_argument("--bootstrap-dir", type=str, default="./output", help="초기 부팅용 과거 shadow/debug CSV 루트(재귀 검색)")
    ap.add_argument("--max-workers", type=str, default="auto")
    ap.add_argument("--daily-h-dir", type=str, default="./output/shadow",
                help="기존 phase1.5 debug 파일(H값 포함) 폴더 경로")
    args = ap.parse_args()

    date_tag = now_seoul_date_str()
    out_csv = Path(args.out or Path("./output") / f"coins_snapshot_{date_tag}.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    excel_out = Path(args.excel_out) if args.excel_out else Path("./output") / f"coins_shadow_{date_tag}.xlsx"
    bootstrap_dir = Path(args.bootstrap_dir) if args.bootstrap_dir else None

    # 1) Top30
    print("[1/4] Selecting Top30 via Phase 1 (exclusions enabled)...")
    df_top = get_top30_binance(n_source=80)  # symbol,name,binance_symbol,market_cap
    print(df_top.head())

    # 2) 병렬 분석
    items = list(df_top.itertuples(index=False))
    max_workers = os.cpu_count() - 1 if args.max_workers == "auto" else int(args.max_workers)
    max_workers = max(1, max_workers)
    print(f"[2/4] Running Phase 1.5 (workers={max_workers})...")

    results: List[dict] = []
    with cf.ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = [
            ex.submit(
                analyze_symbol,
                row.binance_symbol,
                row.name,
                args.lookback_days,
                float(row.market_cap) if pd.notna(row.market_cap) else None,
                bootstrap_dir,
            )
            for row in items
        ]
        for fut in cf.as_completed(futs):
            results.append(fut.result())

    # 3) 스냅샷(시총 내림차순)
    print("[3/4] Building snapshot DataFrame (sort by market_cap desc)...")
    snapshots = [r["snapshot"] for r in results if "snapshot" in r]
    df_snap = pd.DataFrame(snapshots)
    df_err = pd.DataFrame([{"symbol": r.get("symbol"), "error": r.get("error")} for r in results if "error" in r])

    if not df_snap.empty:
        df_snap = df_snap.sort_values(["market_cap", "symbol"], ascending=[False, True], na_position="last")

    df_snap.to_csv(out_csv, index=False)
    print(f"[3.5/4] Saved snapshot → {out_csv}")

    # 4) 통합 Shadow 엑셀 (state/shadow를 직접 시트로)
    print("[4/4] Writing unified shadow Excel (one workbook, tabs per coin)...")
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
            df_snap.to_excel(writer, sheet_name=_safe_sheet_name("SUMMARY", used), index=False)
            for r in results:
                if "state_csv_path" not in r:
                    continue
                p = Path(r["state_csv_path"])
                symbol = (r.get("snapshot") or {}).get("symbol") or p.stem.split("_")[0]
                sheet = _safe_sheet_name(symbol, used)
                try:
                    df_shadow = pd.read_csv(p)
                except Exception:
                    # 비상: 파일 파싱 실패 시 원문 덤프
                    df_shadow = pd.DataFrame({"raw": p.read_text(encoding="utf-8").splitlines()})
                df_shadow.to_excel(writer, sheet_name=sheet, index=False)
        print(f"Saved unified shadow Excel → {excel_out}")

    if not df_err.empty:
        print(f"⚠️ Errors for {len(df_err)} symbols:")
        print(df_err.head())


def run():
    main()


if __name__ == "__main__":
    run()
