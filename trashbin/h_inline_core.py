from dataclasses import dataclass
import pandas as pd

# OMG Phase 1.5 기본 상수
LEVEL_PCTS = [0.44, 0.48, 0.54, 0.59, 0.65, 0.72, 0.79]
RESET_MULTIPLIER = 1.985  # 저점 대비 +98.5% 상승 시 사이클 리셋


@dataclass
class OMGState:
    cycle_low: float
    H: float
    forbidden: int = 7  # 리셋 시 7


def compute_H_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    CSV 없이 메모리상에서 바로 H(사이클 내 최고가)와 상태를 계산합니다.
    입력: df[date, open, high, low, close, volume]
    출력: df[date, H, cycle_low, reset, forbidden_levels_above_last_sell]
    """
    if df.empty:
        cols = ["date", "H", "cycle_low", "reset", "forbidden_levels_above_last_sell"]
        return pd.DataFrame(columns=cols).astype({"H": float, "cycle_low": float, "reset": int, "forbidden_levels_above_last_sell": int})

    st = OMGState(cycle_low=float(df.iloc[0]["low"]), H=float(df.iloc[0]["high"]))
    rows = []

    for _, r in df.iterrows():
        h, l, c = float(r["high"]), float(r["low"]), float(r["close"])  # 성능 고려: 로컬 변수

        # 1) H 루프 보정: 기록 전 고점 확정
        if h > st.H:
            st.H = h

        # 2) 리셋 즉시 적용: 기록 전에 상태 재초기화
        reset = c >= st.cycle_low * RESET_MULTIPLIER
        if reset:
            st.forbidden = 7
            st.cycle_low = l
            st.H = h
        else:
            if l < st.cycle_low:
                st.cycle_low = l

        rows.append({
            "date": r["date"],
            "H": st.H,
            "cycle_low": st.cycle_low,
            "reset": int(reset),
            "forbidden_levels_above_last_sell": st.forbidden,
        })

    return pd.DataFrame(rows)


def compute_current_H(df: pd.DataFrame) -> float:
    """현재 봉 기준 H 한 값만 반환합니다."""
    hs = compute_H_series(df)
    if hs.empty:
        return float("nan")
    return float(hs.iloc[-1]["H"])