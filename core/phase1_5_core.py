#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic — import rules 적용본
- phase1_5_rules.py 를 import 하여 다음을 보장:
  1) 1차 매수 이후에는 바로 다음 레벨(2차)부터 추가 매수 허용 (MIN_LEVEL_GAP_FOR_ADD=1)
  2) 실제 매도 체결가 기준으로, 그 위의 매수 레벨 금지 (동적 forbidden)
  3) forbidden_levels_above_last_sell 집계 정확 수정
- 기존 로직 유지(일봉 OHLC, 최초 매수는 당일 저가로 터치한 레벨 중 가장 깊은 1곳)
- 추가매수는 보유 중 더 깊은 레벨마다 반복 체결(단, 당일 동일 레벨 중복 방지)
"""
import datetime as dt
import time
from typing import Any, Dict, List, Optional
import pathlib
import csv
import requests

# === NEW: rules import ===
from phase1_5_rules import (
    TradeState,
    update_forbidden_after_sell,
    should_execute_buy,
    on_buy_filled,
    on_sell_filled,
)

# ===== 상수 =====
YEARS = 5
TIMEOUT_SEC = 20
BINANCE_BASE = "https://api.binance.com"
URL_KLINES = f"{BINANCE_BASE}/api/v3/klines"

# 단계별 매도 임계치(%) — L 대비 반등률
SELL_THRESHOLDS = {1: 7.7, 2: 17.3, 3: 24.4, 4: 37.4, 5: 52.7, 6: 79.9, 7: 98.5}

# ===== 출력 폴더 보장 =====
OUTPUT_DIR = pathlib.Path("./output")

def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[CORE] OUTPUT_DIR ready: {OUTPUT_DIR.resolve()}", flush=True)

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
    print(f"[CORE] get_binance_1d_ohlc_5y: {binance_symbol}", flush=True)
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
    print(f"[CORE] OHLC rows: {len(rows)}", flush=True)
    return rows

# ===== 레벨 계산(B1~B7) =====

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

# ===== 금지 레벨 카운트 =====

def _forbidden_count_by_state(level_pairs, state: TradeState) -> int:
    """
    금지 레벨 개수 카운트.
    - 매도 이후 첫 매수 전(buys_since_last_sell==0)에는 0으로 간주.
    - 이후에는 last_sell_price 및 금지 인덱스 기준으로 집계.
    """
    if state.last_sell_price is None or getattr(state, "buys_since_last_sell", 0) == 0:
        return 0
    cnt = 0
    for idx, (_nm, p) in enumerate(level_pairs):
        if p >= state.last_sell_price:
            cnt += 1
        elif idx in state.forbidden_levels_above_last_sell:
            cnt += 1
    return cnt

# ===== Phase 1.5 시뮬레이션 =====

def run_phase1_5_simulation(
    symbol: str,
    ohlc: List[Dict[str, Any]],
    seed_H: Optional[float],
    out_csv: pathlib.Path,
    limit_days: int = 180,
    daily_H: Optional[Dict[str, float]] = None,
) -> None:
    """
    - daily_H가 주어지면 각 일자(date)마다 H = daily_H[date] 를 사용(강제 매칭)
      (seed_H는 무시). 일자별로 H가 바뀔 수 있음.
    - daily_H가 없으면 seed_H로 시작(기존 동작).
    - 매수: 저가 기준 레벨 터치
    - 매도: 고가 기준 L 대비 단계별 임계치 도달(전량 매도)
    - 추가매수: 보유 상태에서 더 깊은(미체결) 레벨 터치 시 반복 매수(당일 동일 레벨 1회)
    """

    def fmt(x, nd=8):
        return None if x is None else round(x, nd)

    print(
        f"[CORE] run_phase1_5_simulation: symbol={symbol}, seed_H={seed_H}, daily_H_map={'yes' if daily_H else 'no'}",
        flush=True,
    )

    level_names = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]

    # 초기 H 및 레벨
    H: Optional[float] = None if daily_H else (float(seed_H) if seed_H is not None else None)
    lv = compute_levels(H) if H is not None else None
    level_pairs = (
        sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]) if lv else []
    )

    # 상태 변수
    mode = "high"
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None

    # NEW: TradeState 사용
    state = TradeState()

    # 레벨별 최근 체결 일자 (같은 레벨도 '날짜가 바뀌면' 다시 체결 허용)
    last_fill_date: dict[str, str] = {}

    def ts(ms: int) -> str:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC).strftime("%Y-%m-%d")

    ensure_output_dir()
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date",
                "open",
                "high",
                "low",
                "close",
                "mode",
                "position",
                "stage",
                "event",
                "basis",
                "level_name",
                "level_price",
                "trigger_price",
                "fill_price",
                "H",
                "L_now",
                "rebound_from_L_pct",
                "threshold_pct",
                "forbidden_levels_above_last_sell",
            ]
        )
        for idx, row in enumerate(ohlc):
            # (−1) 첫날 상장일 데이터 무시
            if idx == 0:
                continue

            date = ts(row["closeTime"])
            o = row["open"]
            h = row["high"]
            l = row["low"]
            c = row["close"]

            # 출력용 변수 초기화
            event = ""
            basis = ""
            level_name = ""
            level_price = None
            trigger_price = None
            fill_price = None
            rebound_pct = None
            threshold_pct = None

            # (0) 날짜별 H 강제 적용 (daily_H 모드)
            if daily_H is not None:
                new_H = daily_H.get(date)
                if new_H is not None and (H is None or new_H != H):
                    H = float(new_H)
                    lv = compute_levels(H)
                    level_pairs = sorted(
                        [(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]
                    )
                    # H 업데이트 시, 금지세트 재계산
                    # update_forbidden_after_sell(state, [p for _nm, p in level_pairs])  # 제거: 매도 전까지 forbidden 고정

            # ① 상태 전환 처리
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                mode = "high"
                position = False
                stage = None
                L = None
                last_fill_date.clear()
                # 상승 전환 시 금지세트는 유지 (전략 의도상 유지)

            if mode == "high" and (H is not None) and (l is not None) and (l <= H * 0.56):
                lv = compute_levels(H)
                level_pairs = sorted(
                    [(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]
                )
                mode = "wait"
                L = l
                # 하락 시작 시점에도 금지세트는 상태(state)로 관리되므로 유지

            # ② 최초 매수 — 가장 깊은 레벨 1곳
            buy_happened = False
            if (
                mode == "wait"
                and (not position)
                and (lv is not None)
                and (l is not None)
            ):
                crossed = [
                    (nm, p)
                    for (nm, p) in level_pairs
                    if l <= p
                ]
                if crossed:
                    nm, p = min(crossed, key=lambda x: x[1])  # 가장 깊은 레벨
                    idx_lv = level_names.index(nm)
                    if should_execute_buy(state, idx_lv, p):
                        position = True
                        stage = idx_lv + 1
                        level_name = nm
                        level_price = p
                        basis = "LOW"
                        trigger_price = l
                        fill_price = p
                        L = l
                        event = f"BUY {nm}"

                        last_fill_date[nm] = date
                        on_buy_filled(state, idx_lv, p)

                        w.writerow(
                            [
                                date,
                                round(o, 8),
                                round(h, 8),
                                round(l, 8),
                                round(c, 8),
                                mode,
                                position,
                                stage,
                                event,
                                basis,
                                level_name,
                                round(level_price, 8),
                                round(trigger_price, 8),
                                round(fill_price, 8),
                                round(H, 8) if H is not None else None,
                                round(L, 8) if L is not None else None,
                                None,
                                None,
                                _forbidden_count_by_state(level_pairs, state),
                            ]
                        )
                        buy_happened = True

            # ②-1 추가 매수 — 보유 중 더 깊은 레벨 반복
            if (
                mode == "wait"
                and position
                and (lv is not None)
                and (l is not None)
            ):
                add_candidates = [
                    (nm, p)
                    for (nm, p) in level_pairs
                    if (last_fill_date.get(nm) != date) and (l <= p)
                ]
                for nm, p in sorted(add_candidates, key=lambda x: x[1]):
                    idx_lv = level_names.index(nm)
                    if not should_execute_buy(state, idx_lv, p):
                        continue
                    level_name = nm
                    level_price = p
                    basis = "LOW"
                    trigger_price = l
                    fill_price = p
                    event = f"ADD {nm}"

                    stage = max(stage or 1, idx_lv + 1)
                    L = l if (L is None) else min(L, l)

                    last_fill_date[nm] = date
                    on_buy_filled(state, idx_lv, p)

                    w.writerow(
                        [
                            date,
                            round(o, 8),
                            round(h, 8),
                            round(l, 8),
                            round(c, 8),
                            mode,
                            position,
                            stage,
                            event,
                            basis,
                            level_name,
                            round(level_price, 8),
                            round(trigger_price, 8),
                            round(fill_price, 8),
                            round(H, 8) if H is not None else None,
                            round(L, 8) if L is not None else None,
                            None,
                            None,
                            _forbidden_count_by_state(level_pairs, state),
                        ]
                    )

            # ③ 매도 — 보유 중일 때만
            if position and stage is not None:
                if l is not None:
                    L = l if (L is None) else min(L, l)

                if L is not None and h is not None:
                    rebound_pct = (h / L - 1) * 100.0
                    threshold_pct = SELL_THRESHOLDS.get(stage)
                    if (threshold_pct is not None) and (rebound_pct >= threshold_pct):
                        position = False
                        basis = "HIGH"
                        event = f"SELL S{stage}"

                        target_sell_price = L * (1.0 + (threshold_pct / 100.0))
                        gap_open = (l is not None) and (l >= target_sell_price)
                        trigger_price = target_sell_price
                        fill_price = (o if gap_open else target_sell_price)

                        # rules에 따라 금지 레벨 재계산
                        on_sell_filled(state, fill_price, [p for _nm, p in level_pairs])
                        stage = None
                        L = None
                        last_fill_date.clear()

                        w.writerow(
                            [
                                date,
                                round(o, 8),
                                round(h, 8),
                                round(l, 8),
                                round(c, 8),
                                mode,
                                position,
                                stage,
                                event,
                                basis,
                                level_name,
                                round(level_price, 8) if level_price is not None else None,
                                round(trigger_price, 8),
                                round(fill_price, 8),
                                round(H, 8) if H is not None else None,
                                None,
                                None,
                                threshold_pct,
                                _forbidden_count_by_state(level_pairs, state),
                            ]
                        )
                        continue

            # ④ 상태 스냅샷(일반 기록)
            w.writerow(
                [
                    date,
                    round(o, 8),
                    round(h, 8),
                    round(l, 8),
                    round(c, 8),
                    mode,
                    position,
                    stage,
                    "" if buy_happened else event,
                    basis if buy_happened else "",
                    "" if buy_happened else level_name,
                    round(level_price, 8) if level_price is not None else None,
                    round(trigger_price, 8) if trigger_price is not None else None,
                    round(fill_price, 8) if fill_price is not None else None,
                    round(H, 8) if H is not None else None,
                    round(L, 8) if (position and L is not None) else None,
                    None if rebound_pct is None else round(rebound_pct, 6),
                    threshold_pct,
                    _forbidden_count_by_state(level_pairs, state),
                ]
            )

    # 콘솔 요약
    if limit_days:
        lines = out_csv.read_text(encoding="utf-8").splitlines()
        print(f"[CORE] tail {limit_days}d summary below", flush=True)
        header_skipped = False
        for ln in lines[-limit_days:]:
            parts = ln.split(",")
            if not parts:
                continue
            if not header_skipped and parts[0] == "date":
                header_skipped = True
                continue
            date, _o, _h, _l, close, mode, pos, stg, evt, basis, *_ = parts
            print(
                f" {date} | {close} | {mode} | pos={pos} | stg={stg} | {basis} | {evt}",
                flush=True,
            )
