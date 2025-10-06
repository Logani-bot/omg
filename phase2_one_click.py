#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2.0 — 원클릭 요약 (최종)
- Phase 1 (top30) + Phase 1.5 (core) 통합 오케스트레이터
- 결과물:
  1) 당일 스냅샷 CSV (시가총액 내림차순 정렬)
  2) 통합 Shadow 엑셀(코인별 탭)
- 주의: 개별 shadow CSV는 외부로 저장하지 않습니다(혼동 방지). 내부 상태는 ./state/shadow/*.csv 로만 유지합니다.
"""

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

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


# ---------- Daily H 로더 (Phase 1.5 방식과 동일) ----------
def _normalize_csv_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD 지원
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    # closeTime(ms) → YYYY-MM-DD
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


def load_daily_H_map(csv_path: Path, h_col: str = "H") -> Dict[str, float]:
    """
    기존 shadow(debug) CSV에서 날짜별 H 매핑(YYYY-MM-DD -> float)을 만든다.
    동일 날짜가 여러 번 나오면 '아래쪽(뒤쪽)' 값을 우선한다(가장 나중 기록).
    파일이 없거나 비어있으면 빈 dict 반환.
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return {}
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    if h_col not in rows[0]:
        return {}
    date_col = _pick_date_column(rows[0].keys())
    if not date_col:
        return {}

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


# ---------- 엑셀 시트명 유틸 ----------
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
    import hashlib
    h = hashlib.md5((base or "SHEET").encode()).hexdigest()[:6]
    cand = (base[:24] + "_" + h)[:31]
    used.add(cand)
    return cand


# ---------- 개별 심볼 분석 ----------
def analyze_symbol(binance_symbol: str, name: str, lookback_days: int, market_cap: Optional[float]) -> dict:
    """
    반환:
      {
        'snapshot': {...},                 # 요약행(시가총액 포함, 시장 정렬용)
        'shadow_csv_text': 'date,open,...' # 엑셀 시트로 쓸 전체 CSV 텍스트 (내부 상태 파일 내용)
      }
    또는 에러:
      { 'error': '...', 'symbol': 'BTCUSDT', 'name': 'Bitcoin', 'market_cap': ... }
    """
    try:
        # 1) OHLC (코어 기대 포맷)
        rows = get_binance_1d_ohlc_5y(binance_symbol)
        if not rows:
            raise ValueError(f"No OHLC rows for {binance_symbol}")

        # 2) 내부 상태 shadow 파일 (영속) — 코어가 이 파일을 읽고 이어쓰기
        state_csv = Path(f"./state/shadow/{binance_symbol}_phase1_5_shadow.csv")
        state_csv.parent.mkdir(parents=True, exist_ok=True)
        if not state_csv.exists():
            state_csv.touch()  # 비어있어도 코어가 처리 가능

        # 3) '어제까지'의 날짜별 H 맵 로드 → Phase 1.5와 동일한 H 고정 기준
        daily_H_map = load_daily_H_map(state_csv, h_col="H")

        # 4) seed_H: 최초 1회만 의미 있음(그 이후엔 daily_H가 지배)
        seed_H = float(rows[0]["high"])

        # 5) 코어 실행 (영속 shadow 파일에 이어쓰기)
        run_phase1_5_simulation(
            symbol=binance_symbol,
            ohlc=rows,                  # 필요 시 증분 필터링 가능(지금은 전체 입력해도 daily_H가 기준 고정)
            seed_H=seed_H,
            out_csv=state_csv,          # Path (필수)
            limit_days=lookback_days,
            daily_H=daily_H_map,        # ✅ 날짜별 H 적용(Phase 1.5 방식)
        )

        # 6) 최신 shadow 텍스트 확보 → 마지막 행 파싱
        shadow_text = state_csv.read_text(encoding="utf-8")
        lines = shadow_text.splitlines()

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

        last_price = g("close")
        mode = g("mode", cast=str)
        stage = g("stage", cast=lambda x: int(x) if x not in ("", "None") else 0, default=0)
        next_buy_level = g("next_buy_level_name", cast=str, default="-")
        next_buy_price = g("next_buy_level_price")
        H = g("H")
        L_now = g("L_now")
        rebound_from_L = g("rebound_from_L_pct")
        cutoff = g("cutoff_price")

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
            "market_cap": market_cap,  # 정렬용
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
            "shadow_csv_text": shadow_text,  # 통합 엑셀 시트 작성용
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
    ap.add_argument("--max-workers", type=str, default="auto")
    args = ap.parse_args()

    date_tag = now_seoul_date_str()
    out_csv = Path(args.out or Path("./output") / f"coins_snapshot_{date_tag}.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    excel_out = Path(args.excel_out) if args.excel_out else Path("./output") / f"coins_shadow_{date_tag}.xlsx"

    # 1) Top30 (Phase 1) — 시총 포함
    print("[1/4] Selecting Top30 via Phase 1 (exclusions enabled)...")
    df_top = get_top30_binance(n_source=80)  # columns: symbol,name,binance_symbol,market_cap
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
            )
            for row in items
        ]
        for fut in cf.as_completed(futs):
            results.append(fut.result())

    # 3) 스냅샷 생성 + 시총 내림차순 정렬
    print("[3/4] Building snapshot DataFrame (sort by market_cap desc)...")
    snapshots = [r["snapshot"] for r in results if "snapshot" in r]
    df_snap = pd.DataFrame(snapshots)
    df_err = pd.DataFrame([{"symbol": r.get("symbol"), "error": r.get("error")} for r in results if "error" in r])

    if not df_snap.empty:
        df_snap = df_snap.sort_values(["market_cap", "symbol"], ascending=[False, True], na_position="last")

    df_snap.to_csv(out_csv, index=False)
    print(f"[3.5/4] Saved snapshot → {out_csv}")

    # 4) 통합 Shadow 엑셀(코인별 탭)
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
            # 요약 시트
            df_snap.to_excel(writer, sheet_name=_safe_sheet_name("SUMMARY", used), index=False)
            # 각 코인 시트
            for r in results:
                if "shadow_csv_text" not in r or "snapshot" not in r:
                    continue
                symbol = r["snapshot"].get("symbol") or "SHEET"
                sheet = _safe_sheet_name(symbol, used)
                try:
                    df_shadow = pd.read_csv(io.StringIO(r["shadow_csv_text"]))
                except Exception:
                    df_shadow = pd.DataFrame({"raw": r["shadow_csv_text"].splitlines()})
                df_shadow.to_excel(writer, sheet_name=sheet, index=False)
        print(f"Saved unified shadow Excel → {excel_out}")

    if not df_err.empty:
        print(f"⚠️ Errors for {len(df_err)} symbols:")
        print(df_err.head())


def run():
    main()


if __name__ == "__main__":
    run()
