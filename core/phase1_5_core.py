# core/phase1_5_core.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime as dt
import time
from typing import Any, Dict, List, Optional
import pathlib
import csv

import requests

YEARS = 5
TIMEOUT_SEC = 20
BINANCE_BASE = "https://api.binance.com"
URL_KLINES = f"{BINANCE_BASE}/api/v3/klines"

SELL_THRESHOLDS = {1:7.7, 2:17.3, 3:24.4, 4:37.4, 5:52.7, 6:79.9, 7:98.5}


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
                backoff = min(backoff*1.8, 10)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException:
            time.sleep(backoff)
            backoff = min(backoff*1.8, 10)
    raise RuntimeError("GET failed after retries")


def get_binance_1d_ohlc_5y(binance_symbol: str) -> List[Dict[str, Any]]:
    now_ms = int(dt.datetime.now(dt.UTC).timestamp() * 1000)
    start_ms = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=365*YEARS)).timestamp()*1000)
    rows: List[Dict[str, Any]] = []
    cur = start_ms
    while True:
        data = http_get(URL_KLINES, {
            "symbol": binance_symbol, "interval":"1d",
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
    return rows


def compute_phase1_peak_signal_H(highs: List[float], lows: List[float]) -> Optional[float]:
    """Phase 1 고점 신호(H 확정 후 -44% 이탈로 wait 진입 직전의 high)를 반환.
    반환 H가 없으면 None.
    """
    L: Optional[float] = None
    H: Optional[float] = None
    mode = "none"
    n = min(len(highs), len(lows))
    for i in range(n):
        p = highs[i]
        lo = lows[i]
        if mode == "high":
            cand_H = p if (H is None or (p is not None and p > H)) else H
            if cand_H is not None and lo is not None and lo <= cand_H * 0.56:
                return cand_H
            H = cand_H
            continue
        if lo is not None and (L is None or lo < L):
            L = lo
        if mode == "wait":
            if L is not None and p is not None and p >= L * 1.985:
                H = p
                mode = "high"
                continue
            continue
        if L is not None and p is not None and p >= L * 1.985:
            H = p
            mode = "high"
            continue
        if H is not None and p is not None and p > H:
            H = p
            mode = "high"
            continue
    return None


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


def run_phase1_5_simulation(symbol: str, ohlc: List[Dict[str, Any]], seed_H: float, out_csv: pathlib.Path, limit_days: int = 180) -> None:
    level_names = ["B1","B2","B3","B4","B5","B6","B7"]

    H = float(seed_H)
    lv = compute_levels(H)
    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])

    mode = "wait"
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None
    last_sell_trigger_price: Optional[float] = None
    forbidden_level_prices: set[float] = set()

    def ts(ms:int)->str:
        return dt.datetime.fromtimestamp(ms/1000, tz=dt.UTC).strftime("%Y-%m-%d")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date","open","high","low","close","position","stage","L","rebound_pct","trigger_pct","event","last_sell_trigger_price","allowed_buys_count"])\

        for row in ohlc:
            date = ts(row["closeTime"])
            o=row["open"]; h=row["high"]; l=row["low"]; c=row["close"]
            event = ""

            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                H = h
                mode = "high"
                forbidden_level_prices.clear()
                position=False; stage=None; L=None

            if mode == "high" and h is not None:
                if H is None or h > H:
                    H = h
                if l is not None and H is not None and l <= H * 0.56:
                    lv = compute_levels(H)
                    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                    mode = "wait"
                    L = l

            if mode == "wait" and (not position) and c is not None:
                allowed = [(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices]
                for nm,p in sorted(allowed, key=lambda x: x[1], reverse=True):
                    if c <= p:
                        position=True; stage=level_names.index(nm)+1; L=c; event=f"BUY_FULL@{nm}"; break

            if position and c is not None:
                if l is not None:
                    L = l if (L is None) else min(L,l)
                if L and stage:
                    rebound = (c/L - 1)*100.0
                    trig = SELL_THRESHOLDS.get(stage)
                    if trig is not None and rebound >= trig:
                        position=False; last_sell_trigger_price=c; event=f"SELL_FULL@S{stage}"
                        forbidden_level_prices = {p for (_,p) in level_pairs if last_sell_trigger_price and p > last_sell_trigger_price}
                        stage=None; L=None
                        w.writerow([date,o,h,l,c,position,stage,None,None,trig,event,last_sell_trigger_price,len([(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices])])
                        continue
                    else:
                        w.writerow([date,o,h,l,c,position,stage,(None if L is None else round(L,10)),(None if L is None else round(rebound,6)),trig,event,last_sell_trigger_price,len([(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices])])
                        continue

            if (not position) and l is not None:
                L = l if (L is None) else min(L, l)

            w.writerow([date,o,h,l,c,position,stage,None,None,None,event,last_sell_trigger_price,len([(nm,p) for (nm,p) in level_pairs if p not in forbidden_level_prices])])

    if limit_days:
        lines = out_csv.read_text(encoding="utf-8").splitlines()
        print(f"[PH1.5] 최근 {limit_days}일 요약: date | close | position | stage | L | rebound% | trigger% | event")
        header_skipped=False
        for ln in lines[-limit_days:]:
            parts = ln.split(",")
            if not parts: continue
            if not header_skipped and parts[0]=="date": header_skipped=True; continue
            date,_o,_h,_l,close,pos,stg,Ls,reb,trg,evt,*_ = parts
            print(f" {date} | {close} | {pos} | {stg} | {Ls} | {reb} | {trg} | {evt}")