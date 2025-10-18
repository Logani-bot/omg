#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic — FINAL

요약(필수 스펙)
- wait/high 사이클: high→wait(고점 대비 -44%), wait→high(저점 대비 +98.5% = 재시작)
- 레벨 진입 B1~B7은 H(고점)로부터 고정비율로 산출
- 매수/추매는 wait 모드에서만, 그리고 **당일 범위 포함(low ≤ level ≤ high)** 일 때만 체결
- 스냅샷 행에도 B1~B7, cutoff_price, next_buy_* 및 L_now 항상 기록
- 동일 레벨 재-ADD 금지, 항상 더 깊은 레벨에서만 ADD 허용
- 당일 이벤트는 BUY → ADD → SELL 순으로 정렬 출력, 스냅샷은 마지막 1줄
- 재시작 시점(wait→high)에는 완전 초기화(금지/포지션/스테이지/L/cutoff)
- ✅ SELL 이후에는 L을 **유지** (재시작 전까지 L_now가 공백이 되지 않도록)

CSV 컬럼 (기존 유지 + 보강)
  date,open,high,low,close,
  mode,position,stage,event,basis,
  level_name,level_price,trigger_price,fill_price,
  H,L_now,rebound_from_L_pct,threshold_pct,
  forbidden_levels_above_last_sell,
  B1,B2,B3,B4,B5,B6,B7,
  cutoff_price,next_buy_level_name,next_buy_level_price,next_buy_trigger_price
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any, Dict, List, Optional, Tuple
import pathlib
import csv
import requests

# ===== Constants =====
YEARS = 5
TIMEOUT_SEC = 20
BINANCE_BASE = "https://api.binance.com"
URL_KLINES = f"{BINANCE_BASE}/api/v3/klines"

# SELL thresholds (% rebound from L)
SELL_THRESHOLDS = {1: 7.7, 2: 17.3, 3: 24.4, 4: 37.4, 5: 52.7, 6: 79.9, 7: 98.5}

OUTPUT_DIR = pathlib.Path("./debug")


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ===== HTTP =====

def http_get(url: str, params: Dict[str, Any]) -> Any:
    backoff = 1.0
    for _ in range(6):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SEC)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or (500 <= resp.status_code < 600):
                sleep_sec = float(resp.headers.get("Retry-After") or backoff)
                time.sleep(sleep_sec)
                backoff = min(backoff * 1.8, 10)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException:
            time.sleep(backoff)
            backoff = min(backoff * 1.8, 10)
    raise RuntimeError("GET failed after retries")


# ===== OHLC =====

def get_binance_1d_ohlc_5y(binance_symbol: str) -> List[Dict[str, Any]]:
    now_ms = int(dt.datetime.now(dt.UTC).timestamp() * 1000)
    start_ms = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=365 * YEARS)).timestamp() * 1000)
    rows: List[Dict[str, Any]] = []
    cur = start_ms
    while True:
        data = http_get(
            URL_KLINES,
            {
                "symbol": binance_symbol,
                "interval": "1d",
                "startTime": cur,
                "endTime": now_ms,
                "limit": 1000,
            },
        )
        if not data:
            break
        for k in data:
            rows.append(
                {
                    "openTime": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "closeTime": int(k[6]),
                }
            )
        last = int(data[-1][6])
        if last >= now_ms:
            break
        cur = last + 1
        if len(rows) > 2200:
            break
        time.sleep(0.2)
    if not rows:
        raise RuntimeError("No klines")
    return rows


# ===== Levels =====

def compute_levels(H: float) -> Dict[str, float]:
    return {
        "B1": round(H * 0.56, 10),  # -44%
        "B2": round(H * 0.52, 10),
        "B3": round(H * 0.46, 10),
        "B4": round(H * 0.41, 10),
        "B5": round(H * 0.35, 10),
        "B6": round(H * 0.28, 10),
        "B7": round(H * 0.21, 10),
        "Stop": round(H * 0.19, 10),
    }


# ===== Forbidden display helpers =====

def _forbidden_count(level_pairs, forbidden_level_prices, last_sell_trigger_price):
    if last_sell_trigger_price is None:
        return 0
    cnt = 0
    for _nm, p2 in level_pairs:
        if p2 > last_sell_trigger_price or p2 in forbidden_level_prices:
            cnt += 1
    return cnt


def _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price):
    forb = _forbidden_count(level_pairs, forbidden_level_prices, last_sell_trigger_price)
    allowed = 7 - forb
    if last_sell_trigger_price is None:
        allowed = 7
    if allowed < 0:
        allowed = 0
    if allowed > 7:
        allowed = 7
    return allowed


# ===== Event ordering helpers =====
_level_order = {f"B{i}": i - 1 for i in range(1, 8)}  # B1=0 … B7=6


def _type_order(event: str) -> int:
    # BUY → ADD → SELL
    if not event:
        return 3
    if event.startswith("BUY"):
        return 0
    if event.startswith("ADD"):
        return 1
    if event.startswith("SELL"):
        return 2
    if event.startswith("RESTART"):
        return 9  # 이벤트 행은 맨 끝으로 두더라도 스냅샷 전
    return 3


# ===== Core simulation =====

def run_phase1_5_simulation(
    symbol: str,
    ohlc: List[Dict[str, Any]],
    seed_H: Optional[float],
    out_csv: pathlib.Path,
    limit_days: int = 180,
    daily_H: Optional[Dict[str, float]] = None,
) -> None:
    def ts(ms: int) -> str:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC).strftime("%Y-%m-%d")

    level_names = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]

    # initial H & levels
    H: Optional[float] = None if daily_H else (float(seed_H) if seed_H is not None else None)
    lv = compute_levels(H) if H is not None else None
    level_pairs = (sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]) if lv else [])

    # state
    mode = "high"  # assume prior history
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None
    last_sell_trigger_price: Optional[float] = None
    forbidden_level_prices: set[float] = set()

    # re-ADD guards within a position
    last_fill_date: dict[str, str] = {}
    filled_levels_current: set[str] = set()
    deepest_filled_idx: int = 0

    ensure_output_dir()
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "date","open","high","low","close",
            "mode","position","stage","event","basis",
            "level_name","level_price","trigger_price","fill_price",
            "H","L_now","rebound_from_L_pct","threshold_pct",
            "forbidden_levels_above_last_sell",
            "B1","B2","B3","B4","B5","B6","B7",
            "cutoff_price","next_buy_level_name","next_buy_level_price","next_buy_trigger_price",
        ])

        for idx, row in enumerate(ohlc):
            if idx == 0:
                continue

            date = ts(row["closeTime"])  # UTC → YYYY-MM-DD
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            
            # 2025-10-09 날짜의 저가 데이터를 종가로 대체 (이상 데이터 보정)
            if date == '2025-10-09':
                l = c

            # per-day buffer for event rows
            day_events: List[List[Any]] = []

            def _emit_event(event_row: List[Any]):
                day_events.append(event_row)

            # daily vars
            rebound_pct = None; threshold_pct = None
            restart_event_for_snapshot: Optional[str] = None

            # apply daily_H if given
            if daily_H is not None:
                new_H = daily_H.get(date)
                if new_H is not None and (H is None or new_H != H):
                    H = float(new_H)
                    lv = compute_levels(H)
                    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])

            # Initialize H if not set yet (첫 사이클 시작)
            if H is None and mode == "high" and h is not None:
                H = h
                lv = compute_levels(H)
                level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])

            # high 모드에서 H 갱신 (고점이 H보다 높으면 갱신)
            if mode == "high" and H is not None and h is not None and h > H:
                H = h
                lv = compute_levels(H)
                level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])

            # always track L while in wait (position과 무관)
            if mode == "wait":
                if L is None or (l is not None and l < L):
                    L = l

            # sync guard: if holding and deepest idx < stage, fix it
            if position and (stage is not None) and deepest_filled_idx < stage:
                deepest_filled_idx = stage

            # ========= state transitions =========
            # wait → high (RESTART): H 리셋
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                # capture info before reset
                _prev_L = L
                _restart_trigger = _prev_L * 1.985
                mode = "high"
                # H 리셋: 저점 대비 +98.5% 반등 시 그날 high로 리셋
                H = h
                lv = compute_levels(H)
                level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                forbidden_level_prices.clear()
                position = False
                stage = None
                L = l  # 새 저점 기록
                last_fill_date.clear()
                filled_levels_current.clear()
                deepest_filled_idx = 0
                last_sell_trigger_price = None  # reset cutoff
                # emit explicit RESTART event row so it appears in `event`
                allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)  # 7
                Bvals = [lv[n] if lv else None for n in level_names]
                cutoff = last_sell_trigger_price
                _emit_event([
                    date, round(o,8), round(h,8), round(l,8), round(c,8),
                    mode, position, stage, "RESTART_+98.5pct", "HIGH",
                    "", None, round(_restart_trigger,8), None,
                    (round(H,8) if H is not None else None), None,
                    None, None,
                    allowed_cnt,
                    *(round(x,10) if x is not None else None for x in Bvals),
                    (round(cutoff,10) if cutoff is not None else None),
                    "", None, None,
                ])
                restart_event_for_snapshot = "RESTART_+98.5pct"

            # high → wait (고점 대비 -44%)
            if mode == "high" and (H is not None) and (l is not None) and (l <= H * 0.56):
                lv = compute_levels(H)
                level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                mode = "wait"
                L = l

            # ========= BUY (shallowest among included levels) =========
            if mode == "wait" and (not position) and (lv is not None) and (l is not None) and (h is not None):
                crossed: List[Tuple[str, float]] = [
                    (nm, p) for (nm, p) in level_pairs
                    if (l <= p <= h)
                    and (p not in forbidden_level_prices)
                    and not (last_sell_trigger_price is not None and p > last_sell_trigger_price)
                ]
                if crossed:
                    nm, p = max(crossed, key=lambda x: x[1])  # shallowest (highest price)
                    position = True
                    stage = level_names.index(nm) + 1
                    # emit
                    last_fill_date[nm] = date
                    filled_levels_current = {nm}
                    deepest_filled_idx = stage
                    allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                    Bvals = [lv[n] if lv else None for n in level_names]
                    cutoff = last_sell_trigger_price
                    _emit_event([
                        date, round(o,8), round(h,8), round(l,8), round(c,8),
                        mode, position, stage, f"BUY {nm}", "LOW",
                        nm, round(p,8), round(l,8), round(p,8),
                        (round(H,8) if H is not None else None), (round(L,8) if L is not None else None),
                        None, None,
                        allowed_cnt,
                        *(round(x,10) if x is not None else None for x in Bvals),
                        (round(cutoff,10) if cutoff is not None else None),
                        nm, round(p,10), round(l,10),
                    ])

            # ========= ADD (deeper only; not-yet-filled; included in [l,h]) =========
            if mode == "wait" and position and (lv is not None) and (l is not None) and (h is not None):
                add_candidates: List[Tuple[str, float]] = [
                    (nm, p) for (nm, p) in level_pairs
                    if (last_fill_date.get(nm) != date)
                    and (l <= p <= h)
                    and (p not in forbidden_level_prices)
                    and not (last_sell_trigger_price is not None and p > last_sell_trigger_price)
                    and (nm not in filled_levels_current)
                    and (level_names.index(nm) + 1) > deepest_filled_idx
                ]
                for nm, p in sorted(add_candidates, key=lambda x: _level_order.get(x[0], 99)):
                    stage = max(stage or 1, level_names.index(nm) + 1)
                    last_fill_date[nm] = date
                    filled_levels_current.add(nm)
                    deepest_filled_idx = max(deepest_filled_idx, level_names.index(nm) + 1)
                    allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                    Bvals = [lv[n] if lv else None for n in level_names]
                    cutoff = last_sell_trigger_price
                    _emit_event([
                        date, round(o,8), round(h,8), round(l,8), round(c,8),
                        mode, position, stage, f"ADD {nm}", "LOW",
                        nm, round(p,8), round(l,8), round(p,8),
                        (round(H,8) if H is not None else None), (round(L,8) if L is not None else None),
                        None, None,
                        allowed_cnt,
                        *(round(x,10) if x is not None else None for x in Bvals),
                        (round(cutoff,10) if cutoff is not None else None),
                        nm, round(p,10), round(l,10),
                    ])

            # ========= SELL (only if holding) =========
            if position and stage is not None:
                if l is not None:
                    L = l if (L is None) else min(L, l)  # 계속 저점 추적
                if L is not None and h is not None:
                    rebound_pct = (h / L - 1) * 100.0
                    threshold_pct = SELL_THRESHOLDS.get(stage)
                    if (threshold_pct is not None) and (rebound_pct >= threshold_pct):
                        position = False
                        target_sell_price = L * (1.0 + (threshold_pct / 100.0))
                        gap_open = (l is not None) and (l >= target_sell_price)
                        trigger_price = target_sell_price
                        fill_price = (o if gap_open else target_sell_price)
                        cutoff_price_val = max(target_sell_price, fill_price)
                        last_sell_trigger_price = cutoff_price_val
                        forbidden_level_prices = {
                            p for (_nm, p) in level_pairs
                            if (last_sell_trigger_price is not None) and (p > last_sell_trigger_price)
                        }
                        # SELL 이후에도 L **유지** (재시작 전까지 L_now 공백 방지)
                        stage = None
                        last_fill_date.clear()
                        filled_levels_current.clear()
                        deepest_filled_idx = 0
                        allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                        Bvals = [lv[n] if lv else None for n in level_names]
                        cutoff = last_sell_trigger_price
                        _emit_event([
                            date, round(o,8), round(h,8), round(l,8), round(c,8),
                            mode, position, stage, f"SELL S{stage if stage else ''}".strip(), "HIGH",
                            "", None, round(trigger_price,8), round(fill_price,8),
                            (round(H,8) if H is not None else None), (round(L,8) if L is not None else None),
                            None, threshold_pct,
                            allowed_cnt,
                            *(round(x,10) if x is not None else None for x in Bvals),
                            (round(cutoff,10) if cutoff is not None else None),
                            "", None, None,
                        ])

            # flush events in BUY → ADD → SELL order
            if day_events:
                day_events.sort(key=lambda r: (_type_order(str(r[8])), _level_order.get(str(r[10]), 99)))
                for evr in day_events:
                    w.writerow(evr)

            # ===== snapshot row (always last per day) =====
            # next_* by inclusion rule
            next_nm = ""; next_px: Optional[float] = None; next_trig = l
            if lv is not None and l is not None and h is not None:
                def _is_allowed(px: float) -> bool:
                    if px in forbidden_level_prices:
                        return False
                    if last_sell_trigger_price is not None and px > last_sell_trigger_price:
                        return False
                    return True
                crossed2 = [(nm, px) for (nm, px) in level_pairs if (l <= px <= h) and _is_allowed(px)]
                if crossed2 and mode == "wait":
                    next_nm, next_px = max(crossed2, key=lambda x: x[1])  # shallowest among included
                else:
                    for (nm, px) in level_pairs:
                        if _is_allowed(px) and l > px:
                            next_nm, next_px = nm, px
                            break

            allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
            Bvals = [lv[n] if lv else None for n in level_names]
            cutoff = last_sell_trigger_price

            w.writerow([
                date, round(o,8), round(h,8), round(l,8), round(c,8),
                mode, position, stage,
                restart_event_for_snapshot or "",
                "",
                "",
                None,
                None,
                None,  # fill_price 자리 보존 (열 밀림 방지)
                (round(H,8) if H is not None else None),
                (round(L,8) if L is not None else None),  # L_now
                None if rebound_pct is None else round(rebound_pct, 6),
                threshold_pct,
                allowed_cnt,
                *(round(x,10) if x is not None else None for x in Bvals),
                (round(cutoff,10) if cutoff is not None else None),
                next_nm,
                (round(next_px,10) if next_px is not None else None),
                (round(next_trig,10) if next_trig is not None else None),
            ])

    if limit_days:
        lines = out_csv.read_text(encoding="utf-8").splitlines()
        header_skipped = False
        for ln in lines[-limit_days:]:
            parts = ln.split(",")
            if not parts:
                continue
            if not header_skipped and parts[0] == "date":
                header_skipped = True
                continue
            date, _o, _h, _l, close, mode, pos, stg, evt, basis, *_ = parts
            print(f" {date} | {close} | {mode} | pos={pos} | stg={stg} | {basis} | {evt}")
