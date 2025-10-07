#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 — ONE CLICK (FINAL, OUTPUT version)
- 입력: omg2.py가 생성한 ./data/<symbol>_debug.csv 들
- 결과 저장: ./output 폴더 (snapshot CSV + Excel)
- 의존성 제거: top30 모듈, core 모듈 없이 작동
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import pandas as pd

# -----------------------------
# 기본 경로 설정
# -----------------------------
DATA_DIR = Path("./data")
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_OUT_CSV = OUTPUT_DIR / f"phase2_snapshot_{dt.datetime.now().strftime('%Y%m%d')}.csv"
DEFAULT_XLSX_OUT = OUTPUT_DIR / f"phase2_shadow_{dt.datetime.now().strftime('%Y%m%d')}.xlsx"

# -----------------------------
# 기본 유틸
# -----------------------------

def _is_probable_symbol(tok: str) -> bool:
    if not tok:
        return False
    s = str(tok).strip().upper()
    if not (2 <= len(s) <= 12):
        return False
    if not s[0].isalpha():
        return False
    return all(ch.isalpha() for ch in s)

def _normalize_date(s: str) -> str:
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

def _safe_float(v) -> Optional[float]:
    try:
        if v in (None, "", "None"):
            return None
        return float(str(v).replace(",", ""))
    except Exception:
        return None

def _round(x: Optional[float], n: int) -> Optional[float]:
    return round(x, n) if x is not None else None

def _safe_sheet_name(base: str, used: set) -> str:
    name = (base or "SHEET").strip()[:31]
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

# -----------------------------
# 파일 로드 / 스냅샷 빌더
# -----------------------------

def load_universe(path: Path, prefer_col: Optional[str] = None) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    if path.suffix.lower() == ".txt":
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if _is_probable_symbol(ln)]
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    cols = list(df.columns)
    lower = {c.lower(): c for c in cols}
    if prefer_col and (prefer_col in cols or prefer_col.lower() in lower):
        col = prefer_col if prefer_col in cols else lower[prefer_col.lower()]
        vals = [str(x).strip() for x in df[col].tolist()]
        return [v for v in vals if _is_probable_symbol(v)]
    for cand in ["symbol","ticker","code","base","asset","coin"]:
        if cand in lower:
            col = lower[cand]
            vals = [str(x).strip() for x in df[col].tolist()]
            kept = [v for v in vals if _is_probable_symbol(v)]
            if kept:
                return kept
    # fallback
    toks: List[str] = []
    for c in cols:
        for v in [str(x) for x in df[c].tolist()]:
            for t in v.replace("/",",").replace("|",",").replace(" ",",").split(","):
                t = t.strip()
                if t:
                    toks.append(t)
    return [t for t in toks if _is_probable_symbol(t)]

def find_debug_paths(debug_dir: Path, universe: Optional[List[str]] = None) -> List[Tuple[str, Path]]:
    paths = list(debug_dir.glob("*_debug.csv"))
    if universe:
        index = {p.stem.replace("_debug", "").upper(): p for p in paths}
        out = [(s.strip().upper(), index[s.strip().upper()]) for s in universe if s.strip().upper() in index]
        return out
    return [(p.stem.replace("_debug", "").upper(), p) for p in paths]

def read_debug_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        for k in ["Date","close_time","closeTime","time","Time"]:
            if k in df.columns:
                df.rename(columns={k: "date"}, inplace=True)
                break
    if "date" in df.columns:
        df["date"] = df["date"].map(_normalize_date)
    return df

def snapshot_from_debug(symbol: str, df: pd.DataFrame) -> Dict[str, Optional[float]]:
    if df.empty:
        return {"symbol": symbol, "last_price": None, "mode": None, "H": None, "L": None,
                "drawdown_from_H_pct": None, "rebound_from_L_pct": None, "notes": "EMPTY_DEBUG"}
    last = df.iloc[-1]
    last_price = _safe_float(last.get("close"))
    H = _safe_float(last.get("H"))
    L = _safe_float(last.get("L"))
    mode = str(last.get("mode")) if pd.notna(last.get("mode")) else None
    drawdown = (last_price / H - 1) * 100 if last_price and H else None
    rebound = (last_price / L - 1) * 100 if last_price and L else None
    return {"symbol": symbol, "last_price": _round(last_price, 6), "mode": mode, "H": _round(H, 6),
            "L": _round(L, 6), "drawdown_from_H_pct": _round(drawdown, 3), "rebound_from_L_pct": _round(rebound, 3), "notes": None}

# -----------------------------
# 메인 실행
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Phase2 — one click (output version)")
    ap.add_argument("--universe-file", type=str, default=None)
    ap.add_argument("--universe-col", type=str, default=None)
    ap.add_argument("--debug-dir", type=str, default=str(DATA_DIR))
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT_CSV))
    ap.add_argument("--excel-out", type=str, default=str(DEFAULT_XLSX_OUT))
    args = ap.parse_args()

    debug_dir = Path(args.debug_dir)
    out_csv = Path(args.out)
    xlsx_out = Path(args.excel_out)

    universe = None
    if args.universe_file:
        universe = load_universe(Path(args.universe_file), prefer_col=args.universe_col)
        print(f"[INFO] Universe loaded: {len(universe)} symbols")

    pairs = find_debug_paths(debug_dir, universe)
    if not pairs:
        raise RuntimeError(f"No *_debug.csv files found under {debug_dir}")

    snapshots = []
    engine = None
    try:
        import xlsxwriter; engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl; engine = "openpyxl"
        except Exception:
            pass

    used = set()
    if engine:
        with pd.ExcelWriter(xlsx_out, engine=engine) as writer:
            for i, (symbol, csv_path) in enumerate(pairs, 1):
                try:
                    df = read_debug_csv(csv_path)
                    snap = snapshot_from_debug(symbol, df)
                    snapshots.append(snap)
                    df.to_excel(writer, index=False, sheet_name=_safe_sheet_name(symbol, used))
                    print(f"[RUN] {i}/{len(pairs)} {symbol} → OK ({csv_path.name})")
                except Exception as e:
                    print(f"[SKIP] {symbol}: {e}")
            df_sum = pd.DataFrame(snapshots)
            df_sum.to_excel(writer, index=False, sheet_name=_safe_sheet_name("SUMMARY", used))
        print(f"[DONE] Excel saved → {xlsx_out}")
    else:
        print("[WARN] No Excel engine; skipping Excel export.")

    df_snap = pd.DataFrame(snapshots)
    if not df_snap.empty:
        df_snap = df_snap.sort_values(["symbol"])
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_snap.to_csv(out_csv, index=False)
    print(f"[DONE] Snapshot saved → {out_csv}")

if __name__ == "__main__":
    main()