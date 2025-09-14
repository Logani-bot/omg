"""
Phase 1.5 추가매수/금지레벨 패치 (최종 정리 2025-09-14)
- Rule A: 마지막 매수 레벨보다 위/같은 레벨은 금지. 그 아래 레벨은 모두 허용.
          (예: 1차 매수 후 → 2차, 3차, 4차 ... 모두 허용)
- Rule B: 실제 매도 체결가 기준으로, 그 위의 매수선은 금지.

Integration:
- 이 파일을 `phase1_5_rules.py` 로 저장.
- `phase1_5_core.py` 에서 import 하여 사용.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set

@dataclass
class TradeState:
    position_open: bool = False
    last_buy_level_idx: Optional[int] = None
    last_sell_price: Optional[float] = None
    forbidden_levels_above_last_sell: Set[int] = field(default_factory=set)
    buys_since_last_sell: int = 0  # ▶ 첫 매수 전에는 forbidden 미적용(카운트 0)


def recompute_buy_levels_from_high(high_price: float, grid_pcts: List[float]) -> List[float]:
    """고점(H) 기준 매수 레벨 계산"""
    levels = [high_price * (1 - p/100.0) for p in grid_pcts]
    levels.sort(reverse=True)
    return levels


def update_forbidden_after_sell(state: TradeState, levels: List[float]) -> None:
    """실제 매도가 기준으로 위쪽 레벨을 금지"""
    state.forbidden_levels_above_last_sell.clear()
    if state.last_sell_price is None:
        return
    sell_px = state.last_sell_price
    for idx, lvl_px in enumerate(levels):
        if lvl_px >= sell_px:
            state.forbidden_levels_above_last_sell.add(idx)


def is_level_forbidden(state: TradeState, candidate_idx: int) -> bool:
    """첫 매수 전에는 금지 규칙 미적용"""
    if state.buys_since_last_sell == 0:
        return False
    return candidate_idx in state.forbidden_levels_above_last_sell


def violates_min_gap_for_add(state: TradeState, candidate_idx: int) -> bool:
    """
    Rule A: 마지막 매수 레벨보다 위/같은 레벨은 금지.
    - 예) 마지막 매수 idx=2 → idx<3 (1,2차)은 금지, idx>=3(3차 이후)는 허용
    """
    if not state.position_open or state.last_buy_level_idx is None:
        return False
    required_min_idx = state.last_buy_level_idx + 1
    return candidate_idx < required_min_idx


def should_execute_buy(state: TradeState, candidate_idx: int, candidate_price: float) -> bool:
    """매수 실행 여부 판정"""
    if is_level_forbidden(state, candidate_idx):
        return False
    if violates_min_gap_for_add(state, candidate_idx):
        return False
    return True


def on_buy_filled(state: TradeState, filled_level_idx: int, filled_price: float) -> None:
    """매수 체결 시 상태 업데이트"""
    state.position_open = True
    state.last_buy_level_idx = filled_level_idx
    state.buys_since_last_sell += 1  # 첫 매수 발생 시 forbidden 적용 시작


def on_sell_filled(state: TradeState, filled_price: float, levels: List[float]) -> None:
    """매도 체결 시 상태 업데이트 및 금지세트 갱신"""
    state.position_open = False
    state.last_sell_price = filled_price
    state.last_buy_level_idx = None
    state.buys_since_last_sell = 0  # 다음 사이클 시작 전까지 forbidden 비활성
    update_forbidden_after_sell(state, levels)
