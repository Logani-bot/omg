#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1.5 Core Logic (final, with repeated ADD-buys)
- 날짜별 H(Phase1 결과)를 그대로 사용하여 매수/매도 시뮬레이션
- 매수: 저가 기준(B1~B7 터치) 전량 매수 / '가장 깊은' 레벨에서 1회
- 추가매수(개선): 보유 중 더 깊은 레벨을 터치할 때마다 **해당 레벨마다 반복 매수**
  * 단, 같은 레벨은 1회만 매수(레벨별 중복 방지)
  * 매도선(cutoff) 위 레벨은 금지(기존 규칙 유지)
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
  * mode: high/wait
  * position: 보유 여부
  * stage: 현재 가장 깊은 매수 단계(1~7)
  * event: BUY/ADD/SELL
  * basis: 트리거 기준(LOW/HIGH)
  * trigger_price: 트리거/기준 가격 (BUY/ADD: 당일 저가, SELL: '목표 매도가')
  * fill_price: 체결가 (BUY/ADD: 레벨가 p,
    SELL: 갭오픈이면 시가(o), 아니면 목표가(target_sell_price))

PATCH NOTES (2025-10-05)
- 요청사항 반영하되 **필요 부분만 최소 수정**, 나머지 로직/인터페이스 100% 동일 유지.
1) 사이클 재시작(wait→high, +98.5%) 시 **완전 초기화**에 `last_sell_trigger_price = None` 추가.
2) 스냅샷 보강 컬럼 추가(B1~B7, cutoff_price, next_buy_level_name/price, next_buy_trigger_price) — 기본 컬럼 뒤에만 추가.
3) 표시 규약: `forbidden_levels_above_last_sell` 컬럼은 **허용 레벨 수(0~7)**를 표기.
   - 매도 직후/재시작 직후(차단 없음) → **7**로 표기.
   - 기존 내부 금지 계산 로직은 그대로 두고, 출력 시 7 − 금지개수로 환산.
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

# ===== 금지 카운트(원본 유지) + 허용 수(출력용) =====

def _forbidden_count(level_pairs, forbidden_level_prices, last_sell_trigger_price):
    """금지된 매수 레벨(B1~B7)의 개수."""
    if last_sell_trigger_price is None:
        return 0
    cnt = 0
    for _nm, p2 in level_pairs:
        if p2 > last_sell_trigger_price or p2 in forbidden_level_prices:
            cnt += 1
    return cnt

def _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price):
    """표시 규약: 허용 레벨 수(0~7). 매도 이전(차단 없음)엔 7로 표기."""
    forb = _forbidden_count(level_pairs, forbidden_level_prices, last_sell_trigger_price)
    allowed = 7 - forb
    if last_sell_trigger_price is None:
        allowed = 7
    if allowed < 0:
        allowed = 0
    if allowed > 7:
        allowed = 7
    return allowed

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
    - 추가매수(개선): 보유 상태에서 저가가 더 깊은(아직 미체결) 레벨을 터치할 때, **해당 레벨마다 반복 매수**
    """

    def ts(ms: int) -> str:
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.UTC).strftime("%Y-%m-%d")

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

    # 상태 변수(원본 유지)
    mode = "high"  # 초기: high (과거 히스토리 모름)
    position = False
    stage: Optional[int] = None
    L: Optional[float] = None
    last_sell_trigger_price: Optional[float] = None
    forbidden_level_prices: set[float] = set()

    # ✅ 추가: 레벨별 최근 체결 일자 (같은 레벨도 '날짜가 바뀌면' 다시 체결 허용)
    last_fill_date: dict[str, str] = {}

    ensure_output_dir()
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # === 헤더: 기존 컬럼 유지 + 보강 컬럼 뒤에 추가 ===
        w.writerow([
            "date","open","high","low","close",
            "mode","position","stage","event","basis",
            "level_name","level_price","trigger_price","fill_price",
            "H","L_now","rebound_from_L_pct","threshold_pct",
            # 표시 규약: 허용 레벨 수
            "forbidden_levels_above_last_sell",
            # ▼ 보강 스냅샷 컬럼
            "B1","B2","B3","B4","B5","B6","B7",
            "cutoff_price","next_buy_level_name","next_buy_level_price","next_buy_trigger_price",
        ])

        for idx, row in enumerate(ohlc):
            # (−1) 첫날 상장일 데이터 무시 (원본 유지)
            if idx == 0:
                continue

            date = ts(row["closeTime"])  # UTC → YYYY-MM-DD
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]

            # 출력/이벤트 변수 초기화(원본 유지)
            event = ""; basis = ""; level_name = ""
            level_price = None; trigger_price = None; fill_price = None
            rebound_pct = None; threshold_pct = None

            # (0) 날짜별 H 강제 적용 (daily_H 모드)
            if daily_H is not None:
                new_H = daily_H.get(date)
                if new_H is not None and (H is None or new_H != H):
                    H = float(new_H)
                    lv = compute_levels(H)
                    level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                    # 금지세트 재계산은 매도 시에만 수행 — 원본 유지
            # ▼ L 갱신 로직 (wait 모드에서는 항상 저점 추적)
            if mode == "wait":
                if L is None or l < L:
                    L = l

            # ① 상태 전환 처리 (필요 변경만)
            if mode == "wait" and L is not None and h is not None and h >= L * 1.985:
                mode = "high"
                forbidden_level_prices.clear()
                position = False
                stage = None
                L = None
                last_fill_date.clear()
                # ✅ 추가: 완전 초기화 항목
                last_sell_trigger_price = None  # PATCH-1

            if mode == "high" and (H is not None) and (l is not None) and (l <= H * 0.56):
                lv = compute_levels(H)
                level_pairs = sorted([(nm, lv[nm]) for nm in level_names], key=lambda x: x[1])
                mode = "wait"
                L = l

            # ② 최초 매수 — 가장 깊은 레벨 1곳 (원본 유지)
            buy_happened = False
            if mode == "wait" and (not position) and (lv is not None) and (l is not None):
                crossed = [
                    (nm, p) for (nm, p) in level_pairs
                    if l <= p and p not in forbidden_level_prices
                    and not (last_sell_trigger_price is not None and p > last_sell_trigger_price)
                ]
                if crossed:
                    nm, p = min(crossed, key=lambda x: x[1])  # 가장 깊은 레벨
                    position = True
                    stage = level_names.index(nm) + 1
                    level_name, level_price = nm, p
                    basis, trigger_price, fill_price = "LOW", l, p
                    L = l
                    event = f"BUY {nm}"
                    last_fill_date[nm] = date
                    # ▼ 허용 레벨 수 계산
                    allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                    # ▼ 보강 스냅샷 값 준비
                    Bvals = [lv[n] if lv else None for n in level_names]
                    cutoff = last_sell_trigger_price
                    # next_* (당일 저가 기준)
                    next_nm = nm; next_px = p; next_trig = l
                    w.writerow([
                        date, round(o,8), round(h,8), round(l,8), round(c,8),
                        mode, position, stage, event, basis,
                        level_name, round(level_price,8), round(trigger_price,8), round(fill_price,8),
                        (round(H,8) if H is not None else None), (round(L,8) if L is not None else None),
                        None, None,
                        allowed_cnt,
                        *(round(x,10) if x is not None else None for x in Bvals),
                        (round(cutoff,10) if cutoff is not None else None),
                        next_nm, (round(next_px,10) if next_px is not None else None), (round(next_trig,10) if next_trig is not None else None),
                    ])
                    buy_happened = True

            # ②-1 추가 매수 — 보유 중 더 깊은 레벨 반복 (원본 유지)
            if mode == "wait" and position and (lv is not None) and (l is not None):
                add_candidates = [
                    (nm, p) for (nm, p) in level_pairs
                    if (last_fill_date.get(nm) != date) and (l <= p)
                    and (p not in forbidden_level_prices)
                    and not (last_sell_trigger_price is not None and p > last_sell_trigger_price)
                ]
                for nm, p in sorted(add_candidates, key=lambda x: x[1]):
                    level_name, level_price = nm, p
                    basis, trigger_price, fill_price = "LOW", l, p
                    event = f"ADD {nm}"
                    stage = max(stage or 1, level_names.index(nm) + 1)
                    L = l if (L is None) else min(L, l)
                    last_fill_date[nm] = date
                    # ▼ 허용 레벨 수 + 보강 스냅샷
                    allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                    Bvals = [lv[n] if lv else None for n in level_names]
                    cutoff = last_sell_trigger_price
                    next_nm, next_px, next_trig = nm, p, l
                    w.writerow([
                        date, round(o,8), round(h,8), round(l,8), round(c,8),
                        mode, position, stage, event, basis,
                        level_name, round(level_price,8), round(trigger_price,8), round(fill_price,8),
                        (round(H,8) if H is not None else None), (round(L,8) if L is not None else None),
                        None, None,
                        allowed_cnt,
                        *(round(x,10) if x is not None else None for x in Bvals),
                        (round(cutoff,10) if cutoff is not None else None),
                        next_nm, (round(next_px,10) if next_px is not None else None), (round(next_trig,10) if next_trig is not None else None),
                    ])

            # ③ 매도 — 보유 중일 때만 (원본 유지)
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
                        cutoff_price = max(target_sell_price, fill_price)
                        last_sell_trigger_price = cutoff_price
                        forbidden_level_prices = {
                            p for (_nm, p) in level_pairs
                            if (last_sell_trigger_price is not None) and (p > last_sell_trigger_price)
                        }
                        stage = None
                        L = None
                        last_fill_date.clear()
                        # ▼ 허용 레벨 수 + 보강 스냅샷
                        allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
                        Bvals = [lv[n] if lv else None for n in level_names]
                        cutoff = last_sell_trigger_price
                        # next_*: 매도일은 의미 없음 → 공란 유지
                        w.writerow([
                            date, round(o,8), round(h,8), round(l,8), round(c,8),
                            mode, position, stage, event, basis,
                            level_name if level_name else "", (round(level_price,8) if level_price is not None else None),
                            round(trigger_price,8), round(fill_price,8),
                            (round(H,8) if H is not None else None), None,
                            None, threshold_pct,
                            allowed_cnt,
                            *(round(x,10) if x is not None else None for x in Bvals),
                            (round(cutoff,10) if cutoff is not None else None),
                            "", None, None,
                        ])
                        continue

            # ④ 상태 스냅샷(일반 기록) — 보강 컬럼 포함
            # next_* 계산: 당일 저가 기준으로 '가장 깊은 유효 레벨'을 찾거나, 미통과 시 다음 목표 레벨을 제시
            next_nm = ""; next_px = None; next_trig = l
            if lv is not None and l is not None:
                # 유효 레벨 정의
                def _is_allowed(nm: str, px: float) -> bool:
                    if px in forbidden_level_prices:
                        return False
                    if last_sell_trigger_price is not None and px > last_sell_trigger_price:
                        return False
                    return True
                # 1) 통과 레벨 중 가장 깊은 것
                crossed = [(nm, px) for (nm, px) in level_pairs if l <= px and _is_allowed(nm, px)]
                if crossed and mode == "wait":
                    next_nm, next_px = min(crossed, key=lambda x: x[1])
                else:
                    # 2) 미통과인 경우, 현재가 위쪽 첫 유효 레벨을 안내
                    for (nm, px) in level_pairs:
                        if _is_allowed(nm, px) and l > px:
                            next_nm, next_px = nm, px
                            break

            # 허용 레벨 수 + B1~B7 + cutoff 준비
            allowed_cnt = _allowed_levels_for_display(level_pairs, forbidden_level_prices, last_sell_trigger_price)
            Bvals = [lv[n] if lv else None for n in level_names]
            cutoff = last_sell_trigger_price

            w.writerow([
                date, round(o,8), round(h,8), round(l,8), round(c,8),
                mode, position, stage,
                "" if buy_happened else event,
                basis if buy_happened else "",
                "" if buy_happened else level_name,
                (round(level_price,8) if level_price is not None else None),
                (round(trigger_price,8) if trigger_price is not None else None),
                (round(fill_price,8) if fill_price is not None else None),
                (round(H,8) if H is not None else None),
                (round(L,8) if L is not None else None),
                (None if rebound_pct is None else round(rebound_pct, 6)),
                threshold_pct,
                allowed_cnt,
                *(round(x,10) if x is not None else None for x in Bvals),
                (round(cutoff,10) if cutoff is not None else None),
                next_nm,
                (round(next_px,10) if next_px is not None else None),
                (round(next_trig,10) if next_trig is not None else None),
            ])

    # 콘솔 요약(원본 유지)
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
            print(f" {date} | {close} | {mode} | pos={pos} | stg={stg} | {basis} | {evt}", flush=True)
