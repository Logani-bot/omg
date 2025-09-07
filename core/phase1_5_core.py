#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic
- Phase1의 H 신호(-44% 이탈 후 wait 전환) 기반 매수/매도 시뮬레이션
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
                print(f"[CORE] http {resp.status_code}, retrying in {sleep_sec}s", flush=True)
                time.sleep(sleep_sec)
                backoff = min(backoff * 1.8, 10)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            print(f"[CORE] RequestException: {e}; backoff={backoff}", flush=True)
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

# ===== Phase1: 고점 신호 H 탐지 =====
def compute_phase1_peak_signal_H(highs: List[float], lows: List[float]) -> Optional[float]:
    """
    Phase 1 고점 신호(H 확정 후 -44% 이탈로 wait 진입 직전의 high)를 반환.
    """
    print("[CORE] compute_phase1_peak_signal_H", flush=True)
    L: Optional[float] = None
    H: Optional[float] = None
    mode = "none"  # none / wait / high
    n = min(len(highs), len(lows))
    for i in range(n):
        p = highs[i]; lo = lows[i]
        if mode == "high":
            cand_H = p if (H is None or (p is not None and p > H)) else H
            if cand_H is not None and lo is not None and lo <= cand_H * 0.56:
                print(f"[CORE] peak-signal H found: {cand_H}", flush=True)
                return cand_H
            H = cand_H
            continue
        if lo is not None and (L is None or lo < L):
            L = lo
        if mode == "wait":
            if L is not None and p is not None and p >= L * 1.985:
                H = p; mode = "high"; continue
            continue
        if L is not None and p is not None and p >= L * 1.985:
            H = p; mode = "high"; continue
        if H is not None and p is not None and p > H:
            H = p; mode = "high"; continue
    print("[CORE] peak-signal H not found", flush=True)
    return None

# ===== 레벨 계산 =====
def compute_levels(H: float) -> Dict[str, float]:
    return {
        "B1": round(H*0.56, 10),
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
                            seed_H: float,
                            out_csv: pathlib.Path,
                            limit_days: int = 180) -> None:
    """
    Phase 1 고점 신호(H) 이후 구간에서만 매수/매도 로직 실행.
    - 매수 판단: 당일 저가(low)로 레벨(B1 ~ B7) 터치 여부 확인
    - 매도 판단: 당일 고가(high)로 L 대비 반등률이 임계치 도달 여부 확인
    - 채움가(fill)는 단순화: 레벨 가격(p)로 체결했다고 가정
    """
    print(f"[CORE] run_phase1_5_simulation: symbol={symbol}, seed_H={seed_H}", flush=True)
    level_names = ["B1","B2","B3","B4","B5","B6","B7"]

    def fmt(x, nd=6):
        return None if x is None else round(x, nd)

    # 초기 레벨 동결
    H = float(seed_H)
    lv = compute_levels(H)
    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
    print(f"[CORE] levels from H={H}: {level_pairs}", flush=True)

    mode = "wait"   # Phase1 고점 신호 이후 영역에서만 매매 로직 작동
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
        # 사람이 바로 읽기 쉽게 컬럼 재구성
        w.writerow([
            "date","open","high","low","close","mode",
            "position","stage",
            "event","basis",                # BUY/SELL, 그리고 판단 기준(HIGH/LOW)
            "level_name","level_price",     # 터치한 레벨
            "trigger_price","fill_price",   # 트리거 발생가(저가/고가), 체결가(여기선 레벨가 가정)
            "H","L_now",
            "rebound_from_L_pct","threshold_pct",
            "forbidden_levels_above_last_sell"
        ])

        for row in ohlc:
            date = ts(row["closeTime"])
            o = row["open"]; h = row["high"]; l = row["low"]; c = row["close"]
            event = ""; basis = ""; level_name = ""; level_price = None
            trigger_price = None; fill_price = None
            rebound_pct = None; threshold_pct = None

            # (A) wait 상태에서 +98.5% → high 재개
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                H = h
                mode = "high"
                forbidden_level_prices.clear()
                position=False; stage=None; L=None

            # (B) high 상태에서 -44% 이탈 → wait 재진입(이때 H로 레벨 동결)
            if mode == "high" and h is not None:
                if H is None or h > H:
                    H = h
                if l is not None and H is not None and l <= H * 0.56:
                    lv = compute_levels(H)
                    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                    mode = "wait"
                    L = l

            # (C) 매수: wait 상태 + 미보유 + 당일 저가로 레벨 터치 확인
            if mode == "wait" and (not position) and l is not None:
                allowed = [(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices]
                # 높은 레벨부터 내려오며 체크 (가까운 상단 레벨 먼저 체결 가정)
                for nm, p in sorted(allowed, key=lambda x: x[1], reverse=True):
                    if l <= p:  # 저가가 레벨 밑으로 찍었으면 '터치'
                        position = True
                        stage = level_names.index(nm) + 1  # 1~7
                        level_name = nm
                        level_price = p
                        basis = "LOW"
                        trigger_price = l      # 트리거 발생가 = 당일 저가
                        fill_price = p         # 체결가 = 레벨가(단순화 가정)
                        L = l                  # 매수 직후 L은 당일 저가부터 추적
                        event = f"BUY {nm}"
                        break

            # (D) 보유 중: L 갱신(최저값) + 매도 판단(당일 고가 기준)
            if position:
                # L 갱신
                if l is not None:
                    L = l if (L is None) else min(L, l)
                # 매도 판단 (고가 기준)
                if L is not None and h is not None and stage is not None:
                    rebound_pct = (h / L - 1) * 100.0
                    threshold_pct = SELL_THRESHOLDS.get(stage)
                    if threshold_pct is not None and rebound_pct >= threshold_pct:
                        # 전량 매도
                        position = False
                        basis = "HIGH"
                        event = f"SELL S{stage}"
                        trigger_price = h       # 트리거 발생가 = 당일 고가
                        fill_price = h          # 체결가 = 당일 고가로 단순화
                        last_sell_trigger_price = h
                        # 매도 체결가보다 위의 매수선 금지
                        forbidden_level_prices = {
                            p for (_, p) in level_pairs
                            if last_sell_trigger_price and p > last_sell_trigger_price
                        }
                        stage = None
                        # 매도 후 L 초기화 (다음 사이클 하락 추적을 위해)
                        L = None

                        w.writerow([
                            date, fmt(o,8), fmt(h,8), fmt(l,8), fmt(c,8), mode,
                            position, stage,
                            event, basis,
                            level_name, fmt(level_price,8),
                            fmt(trigger_price,8), fmt(fill_price,8),
                            fmt(H,8), None,
                            None, threshold_pct,
                            len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
                        ])
                        continue
                    else:
                        # 보유 중 경과 기록
                        w.writerow([
                            date, fmt(o,8), fmt(h,8), fmt(l,8), fmt(c,8), mode,
                            position, stage,
                            event, basis,
                            level_name, fmt(level_price,8),
                            fmt(trigger_price,8), fmt(fill_price,8),
                            fmt(H,8), fmt(L,8),
                            fmt(rebound_pct,6), threshold_pct,
                            len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
                        ])
                        continue

            # (E) 미보유 상태에서도 L은 하락 최저치로 갱신해 둔다(다음 +98.5%용)
            if (not position) and l is not None:
                L = l if (L is None) else min(L, l)

            # 일반 상태 기록
            w.writerow([
                date, fmt(o,8), fmt(h,8), fmt(l,8), fmt(c,8), mode,
                position, stage,
                event, basis,
                level_name, fmt(level_price,8),
                fmt(trigger_price,8), fmt(fill_price,8),
                fmt(H,8), None,
                None, None,
                len([1 for (_nm, p) in level_pairs if p not in forbidden_level_prices])
            ])

    # 콘솔 요약
    if limit_days:
        lines = out_csv.read_text(encoding="utf-8").splitlines()
        print(f"[CORE] tail {limit_days}d summary below", flush=True)
        header_skipped=False
        for ln in lines[-limit_days:]:
            parts = ln.split(",")
            if not parts: continue
            if not header_skipped and parts[0]=="date":
                header_skipped=True; continue
            # date|close|pos|stage|basis|event|rebound|thres
            date,_o,_h,_l,close,mode,pos,stg,evt,basis,*rest = parts
            # 안전하게 일부만 보여줌
            print(f" {date} | {close} | {mode} | pos={pos} | stg={stg} | {basis} | {evt}", flush=True)
