# OMG Phase 1.5 거래 시뮬레이션 시스템 완벽 가이드

**작성일**: 2025-11-02
**버전**: 1.0 (최종)
**목적**: 암호화폐 자동 거래신호 생성 및 분석 시스템

---

## 시스템 개요

OMG Phase 1.5는 상태 머신 기반의 암호화폐 거래 시뮬레이션 시스템입니다.

### 입력/출력
- 입력: Binance 5년치 일봉(OHLCV) 데이터
- 처리: Phase 1.5 상태 머신으로 거래 신호 생성
- 출력: CSV/Excel 형식의 거래 기록 및 현재 상태 분석

### 핵심 특징
1. 높은 고점(H) 기준의 비례식 매수 레벨 (B1~B7)
2. 단계별 반등률(%) 기반 매도 (스테이지마다 다름)
3. 추매 금지 규칙: 더 깊은 레벨에서만 추매 가능
4. 금지 레벨 추적: 매도가 이상의 매수 레벨 자동 차단
5. 사이클 리셋: 저점 대비 +98.5% 반등 시 자동 초기화

---

## 전체 시스템 흐름

### 3가지 단계

**Step 1: 우주(Universe) 선택**
- 파일: universe_selector.py
- 역할: CoinGecko에서 Top 100 코인 추출
- 제외: WBTC, WETH, USDT 등 래핑/스테이블 토큰
- 실행: python universe_selector.py --asset coin

**Step 2: 시뮬레이션 생성 (배치 처리)**
- 파일: auto_debug_builder.py
- 역할: 모든 코인에 대해 Phase 1.5 시뮬레이션 실행
- 처리: 데이터 다운로드 → 상태 머신 실행 → CSV/Excel 저장
- 시간: 약 2~5분 (100개 코인 기준)
- 실행: python auto_debug_builder.py

**Step 3: 분석 엑셀 생성**
- 파일: coin_analysis_excel.py
- 역할: 최신 시뮬레이션 결과 분석, 현재 거래 기회 식별
- 실행: python coin_analysis_excel.py
- 출력: output/coin_analysis_20251102_*.xlsx

---

## Phase 1.5 핵심 로직

### 상태 머신 (2가지 모드)

**HIGH 모드**
- 목적: 고점(H) 추적
- H 갱신: 현재 고가 > H 면 업데이트
- 거래: BUY/ADD/SELL 실행 안 됨
- 전환: 저가 ≤ H × 0.56 (-44%) → WAIT 모드

**WAIT 모드**
- 목적: 반등 추적 & 거래 실행
- L 추적: 저가 < L 이면 L 업데이트 (계속 갱신)
- 거래: BUY/ADD/SELL 실행 가능
- 전환: 고가 ≥ L × 1.985 (+98.5%) → RESTART

**RESTART 이벤트**
- 발생: L 대비 +98.5% 반등
- 결과: 사이클 완전 초기화
  - H = 현재 고가로 리셋
  - 모드 = HIGH
  - 위치, 금지레벨, 스테이지 모두 초기화
  - L = 현재 저가

---

## B1~B7 레벨 계산

### 계산 공식
높은 고점 H를 기준으로 고정 비율로 계산:

B1 = H × 0.56  (-44%)
B2 = H × 0.52  (-48%)
B3 = H × 0.46  (-54%)
B4 = H × 0.41  (-59%)
B5 = H × 0.35  (-65%)
B6 = H × 0.28  (-72%)
B7 = H × 0.21  (-79%)
Stop = H × 0.19 (-81%)

### 예시 (H = 100)
B1 = 56.00 (-44%)
B2 = 52.00 (-48%)
B3 = 46.00 (-54%)
B4 = 41.00 (-59%)
B5 = 35.00 (-65%)
B6 = 28.00 (-72%)
B7 = 21.00 (-79%)
Stop = 19.00 (-81%)

---

## 매매 조건

### BUY (첫 진입)
조건:
- mode = "wait"
- position = False
- low ≤ level_price ≤ high (당일 범위)
- level NOT IN forbidden_levels
- 여러 레벨 조건 충족 → 가장 높은 레벨 선택 (shallow)

결과:
- event = "BUY B{n}"
- position = True
- stage = {n}

### ADD (추매)
조건:
- mode = "wait"
- position = True
- low ≤ level_price ≤ high (당일 범위)
- level NOT IN forbidden_levels
- 당일 미충전 상태
- 더 깊은 레벨만 (level_index > deepest_filled_idx) ← 중요!

결과:
- event = "ADD B{n}"
- stage = max(current_stage, new_level_stage)
- filled_levels_current.add({레벨명})

추매 금지 규칙의 의미:
- B1에서 첫 진입 → B2~B7 추매 가능, B1 재진입 불가
- B1→B3 추매 → B4~B7 추매 가능, B1~B3 추매 불가

### SELL (반등 달성)
조건:
- position = True
- rebound_pct = (high / L - 1) × 100
- threshold_pct = SELL_THRESHOLDS[stage]
- rebound_pct ≥ threshold_pct

매도 가격:
- target_sell_price = L × (1 + threshold_pct / 100)
- fill_price = 갭오프닝 여부에 따라

결과:
- event = "SELL S{stage}"
- position = False
- stage = None
- forbidden_levels 업데이트

### 매도 레벨별 반등 임계값
Stage 1: 7.7%
Stage 2: 17.3%
Stage 3: 24.4%
Stage 4: 37.4%
Stage 5: 52.7%
Stage 6: 79.9%
Stage 7: 98.5%

의미: 깊은 진입(B7)일수록 더 큰 반등 필요

### STOP LOSS 조건
조건:
- position = True
- low ≤ H × 0.19 (-81%)

결과:
- event = "STOP LOSS"
- position = False
- 모든 매수 차단 (until RESTART)

---

## 데이터 구조 (27 컬럼 CSV)

### 컬럼 분류
OHLCV: date, open, high, low, close
상태: mode, position, stage, event, basis
거래: level_name, level_price, trigger_price, fill_price
시장: H, L_now, rebound_from_L_pct, threshold_pct
금지레벨: forbidden_levels_above_last_sell
레벨: B1, B2, B3, B4, B5, B6, B7, Stop_Loss
분석: cutoff_price, next_buy_level_name, next_buy_level_price, next_buy_trigger_price

### 컬럼 설명
date: 거래일 (YYYY-MM-DD, UTC)
H: 현재 사이클 최고점
L_now: 현재 사이클 최저점
mode: "high" 또는 "wait"
position: TRUE (보유) / FALSE (미보유)
stage: 1~7 (현재 진입 스테이지)
event: BUY/ADD/SELL/STOP LOSS/RESTART (빈칸은 스냅샷)
rebound_from_L_pct: 현재 반등율 (%)
threshold_pct: 매도 임계값 (%)
forbidden_levels_above_last_sell: 금지된 레벨 수 (0~7)
B1~B7, Stop_Loss: 각 매수/손절 레벨
cutoff_price: 마지막 매도가 (이상의 레벨 금지)
next_buy_level_name: 다음 목표 레벨 (예: B2)
next_buy_level_price: 다음 목표가
next_buy_trigger_price: 다음 트리거가 (현재 저가)

### 행 타입
이벤트 행: event 컬럼에 값이 있음 (BUY, ADD, SELL, STOP LOSS, RESTART)
스냅샷 행: event 컬럼이 빈칸 (매일 마지막 1줄, 일일 상태 기록)

### 행 정렬 순서
1. BUY 이벤트들 (B1→B7 순)
2. ADD 이벤트들 (B1→B7 순)
3. SELL 이벤트
4. STOP LOSS 이벤트
5. RESTART 이벤트
6. 스냅샷 행 (마지막 1줄)

---

## 핵심 알고리즘

### 1. 레벨 계산
def compute_levels(H):
    return {
        "B1": H * 0.56,
        "B2": H * 0.52,
        "B3": H * 0.46,
        "B4": H * 0.41,
        "B5": H * 0.35,
        "B6": H * 0.28,
        "B7": H * 0.21,
        "Stop": H * 0.19,
    }

호출 시점:
- 초기화 시
- H 갱신 시
- RESTART 이벤트 시

### 2. BUY 실행 로직
1. 조건 검증: mode="wait", position=False
2. 포함된 레벨 찾기: low ≤ level ≤ high & NOT forbidden
3. 여러 레벨 조건 충족 시 가장 높은(shallow) 레벨 선택
4. 상태 및 이벤트 기록

### 3. ADD (추매) 실행 로직
1. 조건 검증: mode="wait", position=True
2. 추가 조건: 더 깊은 레벨만 가능 (level_index > deepest_filled_idx)
3. 당일 범위 포함: low ≤ level ≤ high
4. 미충전 상태만: level NOT IN filled_levels_current
5. 깊이순으로 처리

### 4. SELL 실행 로직
1. 저점 추적: L = min(L, low)
2. 반등율 계산: rebound% = (high / L - 1) × 100
3. 임계값 확인: threshold = SELL_THRESHOLDS[stage]
4. 조건 충족 확인: rebound_pct ≥ threshold_pct
5. 매도가 계산: target = L × (1 + threshold_pct/100)
6. 금지 레벨 설정: level > target인 모든 level 금지

### 5. RESTART 이벤트 로직
사이클 완전 초기화:
- mode = "high"
- H = h (현재 고가로 리셋)
- position = False
- stage = None
- L = l (새로운 저점)
- filled_levels_current = {}
- forbidden_level_prices = {} (모든 금지 해제)
- deepest_filled_idx = 0
- last_sell_trigger_price = None

---

## 실전 활용

### 시나리오 1: 전체 시뮬레이션 실행
1. python universe_selector.py --asset coin
2. python auto_debug_builder.py
3. python coin_analysis_excel.py

### 시나리오 2: 특정 코인만 처리
python auto_debug_builder.py --symbols BTCUSDT ETHUSDT

### 시나리오 3: Excel 분석 보기
파일: output/coin_analysis_*.xlsx

컬럼:
- 순위, 코인명, 심볼
- H값 (현재 사이클 최고점)
- B1~B7, Stop_Loss (레벨들)
- 다음매수목표, 목표가격
- 이격도(%) (현재가와 목표가 간격)
- 상태 (거래 상태)

정렬: 가장 가까운 거래 기회 먼저

---

## 주요 제약사항

### 불가능한 시나리오
1. 부분 매도: 단계별로 일부만 매도 불가능
2. 여러 포지션: 동시에 여러 포지션 불가능
3. 손절 후 재진입: STOP LOSS 직후 재진입 불가능

### 동시성 제약
⚠️ NOT thread-safe
- CSV 파일 동시 쓰기 불가능
- Excel 파일 잠금 발생 가능
- 순차 처리만 지원

주의사항:
1. Excel 파일 열어둔 상태에서 스크립트 실행 금지
2. 동시에 여러 스크립트 실행 금지

### API 제약
Binance: 1200 weight/min, 20초 timeout
CoinGecko: ~50 calls/min (비공개)

### 타임존 이슈
Binance API: UTC 반환
CSV: UTC 날짜 저장 (YYYY-MM-DD)
주의: KST와 UTC 표기 혼동 주의

### 성능
100개 코인 시뮬레이션: 약 2~5분
병렬화: 불가능 (CSV 파일 I/O 경합)

최적화:
- 전체 필요 없으면 --top-n 사용
- 특정 코인만 --symbols 사용

---

## 용어 정의

H: 현재 사이클 최고점
L: 현재 사이클 최저점
HIGH 모드: H를 추적하는 모드, 거래 불가
WAIT 모드: L을 추적하며 거래 실행
B1~B7: H로부터 비례식 계산한 7단계 매수 레벨
Stage: 현재 진입한 레벨 번호 (1~7)
Position: 암호화폐 보유 여부
BUY: 첫 진입 거래
ADD: 추가 진입 (Pyramid)
SELL: 반등 조건 만족 시 매도
Rebound %: L 대비 현재 고가의 상승률
Threshold %: Stage별 매도 조건 반등률
Forbidden Level: 거래 불가 매수 레벨
Cutoff Price: 마지막 매도가, 이상의 모든 레벨 금지
RESTART: 사이클 완전 초기화
STOP LOSS: -81% 극단적 손실 시 자동 손절

---

## 최종 요약

### Phase 1.5의 핵심 가치
1. 체계적 진입: 7단계로 분할 진입, 위험 분산
2. 자동 매도: 스테이지별 반등률로 자동 손익 관리
3. 사이클 기반: 큰 반등(+98.5%)으로 자동 초기화
4. 금지 규칙: 이전 매도가 이상의 고가 레벨 자동 차단
5. 손절 자동화: -81% 극단 손실 시 자동 손절

### 사용자의 역할
- 데이터 수집 및 시뮬레이션 자동화
- 거래 신호 생성 및 분석
- 다음 거래 기회 식별
- (실제 거래 실행은 수동)

---

Document Version: 1.0
Last Updated: 2025-11-02
Maintained By: AI Assistant
