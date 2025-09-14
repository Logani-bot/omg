#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic (final)
- 날짜별 H(Phase1 결과)를 그대로 사용하여 매수/매도 시뮬레이션
- 매수: 저가 기준(B1~B7 터치) 전량 매수 / '가장 깊은' 레벨에서 1회
- 추가매수: 보유 중 더 깊은 레벨 터치 시 1회 ADD, stage 갱신
- 매도: 고가 기준(L 대비 단계별 반등률) 전량 매도
- 상태 전환:
  * wait에서 L 대비 +98.5% → high
  * high에서 저가가 H×0.56 이하 → wait (이때의 H로 레벨 동결)
- 재진입 규칙(강화):
  * 매도 발생 후, '차단 기준가' = max(목표 매도가, 실제 체결가)
    - 목표 매도가 = L × (1 + threshold%)
    - cutoff_price = max(target_sell_price, fill_price)
    - 이후 cutoff_price보다 '위'의 매수 레벨은 항상 금지(동적 차단)
- 첫날(상장 첫 캔들) 데이터는 품질 이슈가 잦아 **완전히 무시**하고, 다음 날부터 트래킹 시작
- CSV 컬럼 의미:
  * trigger_price: 트리거/기준 가격 (BUY/ADD: 당일 저가, SELL: '목표 매도가')
  * fill_price: 체결가 (BUY/ADD: 레벨가 p,
                   SELL: 
                       - 갭오픈(당일 저가 ≥ 목표가) : 당일 시가 o
                       - 일반 : 목표가(target_sell_price))
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
    - 상태 전환:
        * wait에서 L 대비 +98.5% → high
        * high에서 저가가 H×0.56 이탈 (레벨 동결은 현재 H로 이미 반영됨)
    """

    def fmt(x, nd=8):
        return None if x is None else round(x, nd)

    print(
        f"[CORE] run_phase1_5_simulation: symbol={symbol}, "
        f"seed_H={seed_H}, daily_H_map={'yes' if daily_H else 'no'}",
        flush=True,
    )

    level_names = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]

    # 초기 H
    H: Optional[float] = None if daily_H else (float(seed_H) if seed_H is not None else None)
    lv = compute_levels(H) if H is not None else None
    level_pairs = (
        sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]) if lv else []
    )

    # 상태 변수
    mode = "high"  # 초기: high (과거 히스토리 모름)
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None
    last_sell_trigger_price: Optional[float] = None
    forbidden_level_prices: set[float] = set()

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

            # ---------------------------
            # ① 상태 전환 처리
            # ---------------------------
            # wait → high : L 대비 +98.5% (고가 기준)
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                mode = "high"
                forbidden_level_prices.clear()
                position = False
                stage = None
                L = None  # 새 사이클 준비

            # high → wait : 저가가 H×0.56 이탈 (레벨 동결은 현재 H로 이미 반영됨)
            if mode == "high" and (H is not None) and (l is not None) and (l <= H * 0.56):
                lv = compute_levels(H)
                level_pairs = sorted(
                    [(nm, lv[nm]) for nm in level_names], key=lambda x: x[1]
                )
                mode = "wait"
                L = l

            # ---------------------------
            # ② 매수 우선 (LOW 기준) — 가장 깊은 레벨 1곳에서만 매수
            # ---------------------------
            buy_happened = False
            if (
                mode == "wait"
                and (not position)
                and (lv is not None)
                and (l is not None)
            ):
                # 당일 저가가 통과한 모든 레벨 수집
                crossed = [
                    (nm, p)
                    for (nm, p) in level_pairs
                    if l <= p and p not in forbidden_level_prices
                ]
                if crossed:
                    # 가장 낮은 가격(= 가장 깊은 레벨) 선택
                    nm, p = min(crossed, key=lambda x: x[1])

                    position = True
                    stage = level_names.index(nm) + 1  # 이 단계가 이후 매도 임계치의 기준이 됩니다
                    level_name = nm
                    level_price = p
                    basis = "LOW"
                    trigger_price = l  # 트리거 = 당일 저가
                    fill_price = p  # 체결가 = 레벨가(단순화)
                    L = l  # 매수 직후 L 시작(당일 저가)
                    event = f"BUY {nm}"  # 필요 시: f"BUY {nm} (crossed {len(crossed)} levels)"

                    # 매수 이벤트를 즉시 기록 (동일 캔들에서 매도 발생 가능성을 허용)
                    w.writerow(
                        [
                            date,
                            fmt(o),
                            fmt(h),
                            fmt(l),
                            fmt(c),
                            mode,
                            position,
                            stage,
                            event,
                            basis,
                            level_name,
                            fmt(level_price),
                            fmt(trigger_price),
                            fmt(fill_price),
                            fmt(H),
                            fmt(L),
                            None,
                            None,
                            len(
                                [
                                    1
                                    for (_nm, p2) in level_pairs
                                    if p2 not in forbidden_level_prices
                                ]
                            ),
                        ]
                    )
                    buy_happened = True

            # ---------------------------
            # ③ 매도 평가 (HIGH 기준) — 반드시 보유 중일 때만
            # ---------------------------
            if position and stage is not None:
                # 보유 중엔 L 유지/갱신
                if l is not None:
                    L = l if (L is None) else min(L, l)

                if L is not None and h is not None:
                    rebound_pct = (h / L - 1) * 100.0
                    threshold_pct = SELL_THRESHOLDS.get(stage)
                    if (threshold_pct is not None) and (rebound_pct >= threshold_pct):
                        # SELL (전량)
                        position = False
                        basis = "HIGH"
                        event = f"SELL S{stage}"

                        # 목표 매도가(이론): L * (1 + threshold)
                        target_sell_price = L * (1.0 + (threshold_pct / 100.0))

                        # 갭오픈 판정: 당일 저가가 목표가 이상이면, 목표가 이하로 내려오지 않음
                        gap_open = (l is not None) and (l >= target_sell_price)

                        # 기록 값
                        trigger_price = target_sell_price  # 트리거는 정확한 목표가
                        fill_price = (
                            o if gap_open else target_sell_price
                        )  # 갭오픈이면 시가 체결, 아니면 목표가 체결

                        # 재진입 차단 기준: 실제 체결가(갭오픈 시 시가)와 목표가 중 더 큰 값으로 차단 기준가 지정
                        cutoff_price = max(target_sell_price, fill_price)
                        last_sell_trigger_price = cutoff_price

                        # (참고용) 정적 금지 세트: '당시' 레벨 중 cutoff보다 위
                        forbidden_level_prices = {
                            p
                            for (_nm, p) in level_pairs
                            if (last_sell_trigger_price is not None) and (p > last_sell_trigger_price)
                        }
                        stage = None
                        L = None

                        w.writerow(
                            [
                                date,
                                fmt(o),
                                fmt(h),
                                fmt(l),
                                fmt(c),
                                mode,
                                position,
                                stage,
                                event,
                                basis,
                                level_name,
                                fmt(level_price),
                                fmt(trigger_price),
                                fmt(fill_price),
                                fmt(H),
                                None,
                                None,
                                threshold_pct,
                                len(
                                    [
                                        1
                                        for (_nm, p2) in level_pairs
                                        if (p2 not in forbidden_level_prices)
                                        and not (
                                            last_sell_trigger_price is not None
                                            and p2 > last_sell_trigger_price
                                        )
                                    ]
                                ),
                            ]
                        )
                        # 매도까지 했으면 이 날은 마무리
                        continue

            # ---------------------------
            # 상태 스냅샷(일반 기록)
            # ---------------------------
            # (주의) 위에서 매수/매도가 한 번이라도 기록됐더라도,
            #       하루 요약 스냅샷도 남겨두고 싶으면 아래를 유지.
            #       만약 이벤트 행만 남기고 싶다면 buy_happened 같은 플래그로 건너뛰기 가능.
            w.writerow(
                [
                    date,
                    fmt(o),
                    fmt(h),
                    fmt(l),
                    fmt(c),
                    mode,
                    position,
                    stage,
                    "" if buy_happened else event,  # 이벤트가 이미 기록됐다면 공백
                    basis if buy_happened else "",
                    "" if buy_happened else level_name,
                    fmt(level_price),
                    fmt(trigger_price),
                    fmt(fill_price),
                    fmt(H),
                    fmt(L) if position else None,
                    None if rebound_pct is None else round(rebound_pct, 6),
                    threshold_pct,
                    len(
                        [
                            1
                            for (_nm, p2) in level_pairs
                            if (p2 not in forbidden_level_prices)
                            and not (
                                last_sell_trigger_price is not None
                                and p2 > last_sell_trigger_price
                            )
                        ]
                    ),
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
