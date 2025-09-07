#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic
- 날짜별 H(Phase1 결과)를 그대로 사용하여 매수/매도 시뮬레이션
- 매수: 저가 기준(B1~B7 터치) 전량 매수
- 매도: 고가 기준(L 대비 단계별 반등률) 전량 매도
- 상태 전환:
  * wait에서 L 대비 +98.5% → high
  * high에서 저가가 H×0.56 이하 → wait (이때의 H로 레벨 동결)
"""

import datetime as dt
import time
from typing import Any, Dict, List, Optional
import pathlib
import csv
import requests

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
    start_ms = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=365*YEARS)).timestamp()*1000)
    rows: List[Dict[str, Any]] = []
    cur = start_ms
    while True:
        data = http_get(URL_KLINES, {
            "symbol": binance_symbol, "interval": "1d",
            "startTime": cur, "endTime": now_ms, "limit": 1000
        })
        if not data:
            break
        for k in data:
            rows.append({
                "openTime": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "closeTime": int(k[6]),
            })
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
        "B1": round(H*0.56, 10),  # -44%
        "B2": round(H*0.52, 10),
        "B3": round(H*0.46, 10),
        "B4": round(H*0.41, 10),
        "B5": round(H*0.35, 10),
        "B6": round(H*0.28, 10),
        "B7": round(H*0.21, 10),
        "Stop": round(H*0.19, 10)
    }

# ===== Phase 1.5 시뮬레이션 =====
def run_phase1_5_simulation(symbol: str,
                            ohlc: List[Dict[str, Any]],
                            seed_H: Optional[float],
                            out_csv: pathlib.Path,
                            limit_days: int = 180,
                            daily_H: Optional[Dict[str, float]] = None) -> None:
    """
    - daily_H가 주어지면 각 일자(date)마다 H = daily_H[date] 를 사용(강제 매칭)
      (seed_H는 무시). 일자별로 H가 바뀔 수 있음.
    - daily_H가 없으면 seed_H로 시작(기존 동작).
    - 매수: 저가 기준 레벨 터치
    - 매도: 고가 기준 L 대비 단계별 임계치 도달(전량 매도)
    - 상태 전환:
        * wait에서 L 대비 +98.5% → high
        * high에서 저가가 H×0.56 이하 → wait (해당 시점 H로 레벨 동결)
    """
    def fmt(x, nd=8):
        return None if x is None else round(x, nd)

    print(f"[CORE] run_phase1_5_simulation: symbol={symbol}, "
          f"seed_H={seed_H}, daily_H_map={'yes' if daily_H else 'no'}", flush=True)

    level_names = ["B1","B2","B3","B4","B5","B6","B7"]

    # 초기 H 설정
    H: Optional[float] = None if daily_H else (float(seed_H) if seed_H is not None else None)
    lv = compute_levels(H) if H is not None else None
    level_pairs = (sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]) if lv else [])

    # 상태 변수
    mode = "high"     # 초기: high (과거 히스토리 모름)
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None
    last_sell_trigger_price: Optional[float] = None
    forbidden_level_prices: set[float] = set()

    def ts(ms:int)->str:
        return dt.datetime.fromtimestamp(ms/1000, tz=dt.UTC).strftime("%Y-%m-%d")

    ensure_output_dir()
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "date","open","high","low","close","mode",
            "position","stage",
            "event","basis",
            "level_name","level_price",
            "trigger_price","fill_price",
            "H","L_now",
            "rebound_from_L_pct","threshold_pct",
            "forbidden_levels_above_last_sell"
        ])

        for row in ohlc:
            date = ts(row["closeTime"])
            o=row["open"]; h=row["high"]; l=row["low"]; c=row["close"]
            event = ""; basis = ""
            level_name = ""; level_price = None
            trigger_price = None; fill_price = None
            rebound_pct = None; threshold_pct = None

            # (0) 날짜별 H 강제 적용 (daily_H 모드)
            if daily_H is not None:
                new_H = daily_H.get(date)
                if new_H is not None:
                    if (H is None) or (new_H != H):
                        H = float(new_H)
                        lv = compute_levels(H)
                        level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])

            # (1) wait → high 전환(+98.5%)
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                mode = "high"
                forbidden_level_prices.clear()
                position=False; stage=None; L=None

            # (2) high 상태에서 -44% 이탈 시 wait 전환(레벨 동결)
            if mode == "high" and (H is not None) and (h is not None):
                if (l is not None) and (l <= H * 0.56):
                    # 현 H로 레벨 동결
                    lv = compute_levels(H)
                    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                    mode = "wait"
                    L = l

            # (3) 매수: wait + 미보유 + 저가로 레벨 터치
            if mode == "wait" and (not position) and (lv is not None) and (l is not None):
                allowed = [(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices]
                for nm,p in sorted(allowed, key=lambda x: x[1], reverse=True):
                    if l <= p:
                        position = True
                        stage = level_names.index(nm) + 1
                        level_name = nm
                        level_price = p
                        basis = "LOW"
                        trigger_price = l      # 저가가 트리거
                        fill_price = p         # 체결가 = 레벨가(단순화)
                        L = l                  # 매수 직후 L 시작
                        event = f"BUY {nm}"
                        break

            # (4) 보유 중: L 갱신 + 매도 판단(고가 기준)
            if position:
                if l is not None:
                    L = l if (L is None) else min(L, l)
                if L is not None and h is not None and stage is not None:
                    rebound_pct = (h / L - 1) * 100.0
                    threshold_pct = SELL_THRESHOLDS.get(stage)
                    if (threshold_pct is not None) and (rebound_pct >= threshold_pct):
                        # 전량 매도
                        position = False
                        basis = "HIGH"
                        event = f"SELL S{stage}"
                        trigger_price = h
                        fill_price = h
                        last_sell_trigger_price = h
                        # 매도 체결가보다 위의 매수선 금지
                        forbidden_level_prices = {
                            p for (_, p) in level_pairs
                            if last_sell_trigger_price and p > last_sell_trigger_price
                        }
                        stage = None
                        L = None

                        w.writerow([
                            date, fmt(o), fmt(h), fmt(l), fmt(c), mode,
                            position, stage,
                            event, basis,
                            level_name, fmt(level_price),
                            fmt(trigger_price), fmt(fill_price),
                            fmt(H), None,
                            None, threshold_pct,
                            len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
                        ])
                        continue
                    else:
                        # 보유 유지 상태 기록
                        w.writerow([
                            date, fmt(o), fmt(h), fmt(l), fmt(c), mode,
                            position, stage,
                            event, basis,
                            level_name, fmt(level_price),
                            fmt(trigger_price), fmt(fill_price),
                            fmt(H), fmt(L),
                            None if rebound_pct is None else round(rebound_pct,6),
                            threshold_pct,
                            len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
                        ])
                        continue

            # (5) 미보유 시에도 L은 최저치로 갱신(다음 +98.5% 탐지용)
            if (not position) and (l is not None):
                L = l if (L is None) else min(L, l)

            # 일반 상태 기록
            w.writerow([
                date, fmt(o), fmt(h), fmt(l), fmt(c), mode,
                position, stage,
                event, basis,
                level_name, fmt(level_price),
                fmt(trigger_price), fmt(fill_price),
                fmt(H), None,
                None, None,
                len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
            ])

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
            date,_o,_h,_l,close,mode,pos,stg,evt,basis,*_ = parts
            print(f" {date} | {close} | {mode} | pos={pos} | stg={stg} | {basis} | {evt}", flush=True)
