# OMG 프로젝트 전체 모니터링 시스템 정리

## 📊 시스템 개요

OMG 프로젝트에는 **총 3개의 독립적인 모니터링 시스템**이 있습니다:

1. **Envelope 근접 알림** (Red S/envelope_alert.py)
2. **업비트 급락 감시** (Red S/upbit_monitor.py)
3. **Phase 1.5 실시간 감시** (미구현, 구성 요소만 존재)

---

## 1️⃣ Envelope 근접 알림 시스템

### 📌 기본 정보
- **파일**: `Red S/envelope_alert.py`
- **실행 주기**: **10분 간격** (기본값)
- **대상**: Binance USDT 페어 Top 30 코인
- **거래소**: Binance
- **실행 스크립트**: `Old/envelope_monitor_loop.py`

### 📈 감시 기준
```
Envelope 계산:
- 기간: 45일 이동평균
- 상단선: MA × 1.45 (+45%)
- 하단선: MA × 0.55 (-45%)

알림 조건:
- 현재가가 하단선 5% 이내 접근 시 알림
- Top 30 코인만 감시
```

### 🔔 알림 예시
```
🚨 Red S 근접 알림 🚨
━━━━━━━━━━━━━━━━━━━━

1. Ethereum (ETH)
   - 현재가: $2,456.7800
   - 하단선: $2,380.5600
   - 이격도: 3.20%
```

### 💾 출력 파일
- `output/envelope_all_coins_YYYYMMDD_HHMMSS.xlsx`
- `output/envelope_alerts_YYYYMMDD_HHMMSS.xlsx` (알림 대상만)

### ⚙️ 설정
```python
# Red S/envelope_alert.py
ENVELOPE_DAYS = 45  # 45일 이동평균
ALPHA = 0.45  # ±45% 폭
PROXIMITY_THRESHOLD = 0.05  # 5% 이내 알림

# .env
MONITOR_INTERVAL_MINUTES=10
```

---

## 2️⃣ 업비트 급락 감시 시스템

### 📌 기본 정보
- **파일**: `Red S/upbit_monitor.py`
- **실행 주기**: **1시간 간격** (매시간 정각)
- **대상**: 업비트 전체 KRW 마켓
- **거래소**: 업비트
- **실행 스크립트**: `Red S/run_monitor.py`

### 📈 감시 기준
```
모니터링 대상:
- 업비트 KRW 페어 전체 코인
- 실시간 티커 API 사용

알림 조건:
- 전일대비 -15% 이상 하락 종목이 15개 이상
- 시작 알림: 15개 이상 발생 시 (하루 1회)
- 끝 알림: 15개 미만으로 감소 시 (하루 1회)
```

### 🔔 알림 예시
```
🚨 업비트 급락 알림 🚨

📊 현재 -15% 이하 하락 종목: 18개
⏰ 알림 시간: 2025-01-XX 14:30:00

📉 상위 하락 종목 (상위 10개):
 1. 비트코인 (BTC)
    💰 가격: 52,000,000원
    📉 등락률: -18.50%
    💸 등락가: -9,800,000원
```

### 💾 출력 파일
- `Red S/upbit_monitor_YYYYMMDD.log`
- `Red S/alert_status.json` (알림 상태 기록)

### ⚙️ 설정
```json
// Red S/config.json
{
  "decline_threshold": -15.0,  // 15% 이상 하락
  "min_coin_count": 15,        // 15개 이상
  "check_interval_hours": 1,   // 1시간 간격
  "log_level": "INFO"
}
```

---

## 3️⃣ Phase 1.5 시스템 (실시간 감시 미구현)

### 📌 기본 정보
- **핵심 로직**: `core/phase1_5_core.py`
- **엑셀 생성**: `coin_analysis_excel.py`
- **디버그 빌더**: `auto_debug_builder.py`
- **현재 상태**: ✅ 구성 요소 존재, ❌ 실시간 감시 미구현

### 📈 매수/매도 레벨

#### Phase 1.5 매수 레벨 (B1~B7)
```
고점(H) 기준으로 계산:
- B1: H × 0.56  (-44%)  - 1차 매수
- B2: H × 0.52  (-48%)  - 2차 매수
- B3: H × 0.46  (-54%)  - 3차 매수
- B4: H × 0.41  (-59%)  - 4차 매수
- B5: H × 0.35  (-65%)  - 5차 매수
- B6: H × 0.28  (-72%)  - 6차 매수
- B7: H × 0.21  (-79%)  - 7차 매수

손절선:
- Stop: H × 0.19  (-81%)
```

#### Phase 1.5 매도 레벨 (S1~S7)
```
저점(L) 기준 반등률:
- S1: +7.7%  - 1차 매도
- S2: +17.3% - 2차 매도
- S3: +24.4% - 3차 매도
- S4: +37.4% - 4차 매도
- S5: +52.7% - 5차 매도
- S6: +79.9% - 6차 매도
- S7: +98.5% - 7차 매도 (전량 매도)
```

### 🎯 사이클 로직
```
상태 전환:
- none/wait → high: L 대비 +98.5% 상승 시
- high → wait: H 대비 -44% 하락 시

매수 조건:
- wait 모드에서만 매수 가능
- 당일 저가가 매수선 통과 시 체결
- 더 깊은 레벨에서만 추가 매수

매도 조건:
- 저점 대비 반등률 도달 시 전량 매도
- 단계별 반등률 적용
```

### 💾 출력 파일
- `debug/{SYMBOL}_debug.csv` - 시뮬레이션 결과
- `output/coin_analysis_YYYYMMDD_HHMMSS.xlsx` - 현재 상태 분석

### ⚙️ 실행 방법
```bash
# 디버그 파일 생성 (1회성)
python auto_debug_builder.py

# 엑셀 분석 생성
python coin_analysis_excel.py

# Phase 1.5 시뮬레이션 (단일 코인)
python -u Old/run_phase1_5.py --symbol SUI --limit-days 180
```

---

## 🔍 감시 기준 비교표

| 시스템 | 기준 | 계산 방법 | 알림 조건 |
|--------|------|----------|-----------|
| **Envelope** | 이동평균 기반 | 45일 MA ± 45% | 하단선 5% 이내 |
| **업비트 급락** | 등락률 | 전일 대비 % | -15% 이상 15개 |
| **Phase 1.5** | 고점/저점 기반 | H/L 기준 % | 레벨별 접근 |

---

## 🎯 감시 대상 별 차이

### Envelope 시스템
```
데이터: 일봉 OHLCV (Binance)
범위: Top 30 코인
목적: 매수 기회 포착
감시 대상: 하단선 근접
주기: 10분
```

### 업비트 급락
```
데이터: 실시간 티커 (업비트)
범위: 전체 KRW 마켓
목적: 시장 급락 감지
감시 대상: -15% 이상 하락
주기: 1시간
```

### Phase 1.5
```
데이터: 일봉 OHLCV (Binance)
범위: Top 100 코인
목적: 단계별 매수/매도
감시 대상: B1~B7, S1~S7 레벨
주기: 미구현 (수동 실행)
```

---

## 🚀 실제 사용 중인 시스템

### ✅ 활성 모니터링 (24/7)
1. **Red S/envelope_alert.py** - Envelope 근접 알림
2. **Red S/upbit_monitor.py** - 업비트 급락 감시

### ⚠️ 일회성 실행
3. **auto_debug_builder.py** - 디버그 CSV 생성 (수동)
4. **coin_analysis_excel.py** - 엑셀 분석 생성 (수동)

---

## 📊 Phase 1.5 실시간 감시 추가 가능

### 현재 상태
- ✅ Phase 1.5 로직 완성 (`core/phase1_5_core.py`)
- ✅ 디버그 파일 생성 기능
- ✅ 엑셀 분석 기능
- ❌ **실시간 모니터링 미구현**

### 구현 필요 사항
```python
# 예상 구현
class Phase15RealtimeMonitor:
    def __init__(self):
        self.debug_data = {}  # debug/{SYMBOL}_debug.csv 로드
        self.targets = {}     # 다음 매수 목표 저장
    
    def check_level(self, symbol, current_price):
        """현재가와 매수/매도 레벨 비교"""
        # B1~B7, S1~S7 체크
        # 알림 전송
    
    def run_monitoring(self):
        """주기별 실행"""
        # 10분 간격으로 체크
        # 조건 충족 시 알림
```

### 추가 작업
1. 실시간 모니터 스크립트 작성
2. B1~B7, S1~S7 접근 감지
3. 텔레그램 알림 연동
4. 배치 파일 생성

---

## 💡 권장 구성

### 현 시점 (2개 시스템)
```
주기적으로 실행:
1. Envelope: 10분 간격
2. 업비트: 1시간 간격

수동 실행:
3. Phase 1.5: 일일 1회 또는 필요 시
```

### 완전 자동화 (3개 시스템)
```
주기적으로 실행:
1. Envelope: 10분 간격
2. 업비트: 1시간 간격
3. Phase 1.5: 10분 간격 (구현 필요)
```

---

## 🔧 환경 변수 통합

### .env 파일 (통합)
```env
# 공통
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# Envelope
MONITOR_INTERVAL_MINUTES=10
SAVE_EXCEL_EVERY_N_RUNS=6

# 업비트
DECLINE_THRESHOLD=-15.0
MIN_COIN_COUNT=15

# Phase 1.5 (향후)
PHASE15_MONITOR_INTERVAL=600
PHASE15_ALERT_DISTANCE=0.05
```

---

## 📝 요약

### 현재 운영 중
- ✅ **Envelope**: 일봉 기반, 10분 주기
- ✅ **업비트 급락**: 실시간, 1시간 주기

### 데이터 기반 분석
- ✅ **Phase 1.5**: 일봉 기반, 수동 실행
- ❌ **Phase 1.5 실시간**: 미구현

### 차이점
- **Envelope**: 장기 추세 (45일 MA)
- **Phase 1.5**: 고점/저점 기반 레벨
- **업비트**: 단기 급락 감지

---

**마지막 업데이트**: 2025-01-XX  
**작성자**: OMG Trading System


