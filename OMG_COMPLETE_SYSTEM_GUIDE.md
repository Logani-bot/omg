# OMG 완전 시스템 가이드

**Phase 1.5 기반 암호화폐 자동 트레이딩 신호 시스템**

---

## 📋 시스템 개요

OMG 시스템은 **2단계 자동화 시스템**입니다:

### 1단계: 매일 00:10 - 자동 배치 분석
- Top 100 코인 5년 백테스팅
- Phase 1.5 시뮬레이션 실행
- Debug 파일 + Analysis Excel 생성

### 2단계: 24/7 실시간 감시
- Debug 파일 기반 매수선 추적
- 바이낸스 실시간 가격 조회
- 매수 기회 근접 시 텔레그램 알림

---

## 🔄 전체 워크플로우

```
00:10 자동 실행
    ↓
universe_selector.py (Top 100 코인)
    ↓
auto_debug_builder.py (5년 백테스팅)
    ↓
debug/*.csv (100개 파일 생성)
    ↓
coin_analysis_excel.py (분석 Excel)
    ↓
output/coin_analysis_YYYYMMDD_HHMMSS.xlsx
    ↓
crypto_realtime_monitor.py (실시간 감시 시작)
    ↓
30분마다 체크 → 바이낸스 API
    ↓
매수선 5% 이내 → 텔레그램 알림
```

---

## 📁 핵심 파일 구조

### 배치 분석 (00:10)

**1. universe_selector.py**
- CoinGecko에서 Top 100 코인 추출
- 래핑 토큰/스테이블코인 제외
- 출력: 코인 리스트

**2. auto_debug_builder.py**
- 각 코인별 5년 일봉 데이터 수집 (Binance)
- Phase 1.5 시뮬레이션 실행
- 출력: `debug/{SYMBOL}_debug.csv` (100개 파일)

**3. coin_analysis_excel.py**
- Debug CSV에서 최신 상태 읽기
- CoinGecko 현재가 조회
- 다음 매수 레벨 계산
- 출력: `output/coin_analysis_{timestamp}.xlsx`

### 실시간 감시 (24/7)

**4. crypto_realtime_monitor.py** ⭐
- 00:10에 Analysis Excel 로드
- 30분마다 바이낸스 현재가 조회
- B1~B7 레벨 5% 이내 접근 시 알림
- 중복 알림 방지 (코인별, 레벨별 하루 1회)
- 출력: 텔레그램 메시지 + `alert_history.json`

---

## ⏰ 자동 실행 스케줄

### 매일 00:10 - 배치 분석

**Windows Task Scheduler 설정:**

```
작업명: OMG_Daily_Analysis
트리거: 매일 00:10
동작: C:\Coding\omg\run_daily_analysis.bat
```

**run_daily_analysis.bat 내용:**
```batch
@echo off
cd /d C:\Coding\omg
python auto_debug_builder.py --limit-days 1200
python coin_analysis_excel.py
echo Daily analysis completed at %date% %time%
```

### 24/7 - 실시간 감시

**방법 1: 부팅 시 자동 시작 (권장)**

```
작업명: OMG_Realtime_Monitor
트리거: 컴퓨터 시작 시
동작: C:\Coding\omg\run_realtime_monitor.bat
조건: ❌ AC 전원일 때만 (해제)
```

**run_realtime_monitor.bat 내용:**
```batch
@echo off
cd /d C:\Coding\omg
python crypto_realtime_monitor.py
```

**방법 2: 수동 시작**
```bash
cd C:\Coding\omg
python crypto_realtime_monitor.py
```

---

## 🎯 crypto_realtime_monitor.py 동작 원리

### 초기화 (00:10)

```python
1. OMG 디렉토리 이동
2. auto_debug_builder.py 실행
3. coin_analysis_excel.py 실행
4. 최신 coin_analysis_*.xlsx 파일 로드
5. 각 코인의 매수 레벨 (B1~B7) 저장
6. alert_history.json 로드 (중복 방지용)
```

### 30분마다 실행

```python
for 각 코인 in 모니터링_리스트:
    # 1. 현재가 조회 (Binance API)
    current_price = get_binance_price(symbol)

    # 2. 다음 매수 레벨 확인
    next_target = monitoring_data[symbol]['next_target']

    # 3. 거리 계산
    distance_pct = (current_price - next_target) / next_target * 100

    # 4. 5% 이내 && 중복 아니면 알림
    if distance_pct <= 5.0:
        if not already_sent_today(symbol, next_target):
            send_telegram_alert(symbol, current_price, next_target)
            save_alert_history(symbol, next_target)
```

### 알림 메시지 예시

```
🟡 OMG 매수 알림

코인: BTC (Bitcoin)
순위: #1
현재가: $42,150
매수목표: B2 $40,000
거리: -5.1%

⚠️ 매수선 5% 이내 접근!
```

---

## 📊 Debug CSV 구조 (27개 컬럼)

**coin_analysis_excel.py가 읽는 컬럼:**
- `next_buy_level_name`: B1, B2, ..., B7
- `next_buy_level_price`: 다음 매수 목표가
- `H`: 현재 사이클 최고가
- `mode`: high / wait
- `position`: TRUE / FALSE

**crypto_realtime_monitor.py가 사용하는 데이터:**
```python
{
    "BTC": {
        "rank": 1,
        "name": "Bitcoin",
        "next_target": "B2",  # 다음 매수 레벨
        "target_price": 40000.0,  # 매수 목표가
        "buy_levels": {
            "B1": 44000,
            "B2": 40000,
            "B3": 36000,
            ...
        }
    }
}
```

---

## 🔔 알림 시스템

### 알림 조건

```python
# 5% 이내 접근
distance = (current_price - target_price) / target_price * 100

if distance <= 5.0:
    send_alert()
```

### 중복 방지 로직

**alert_history.json 구조:**
```json
{
  "BTC": {
    "B2": "2025-11-02"
  },
  "ETH": {
    "B1": "2025-11-02",
    "B3": "2025-11-01"
  }
}
```

**중복 체크:**
```python
def already_sent_today(symbol, target):
    if symbol in alert_history:
        if target in alert_history[symbol]:
            sent_date = alert_history[symbol][target]
            return sent_date == today
    return False
```

---

## 🚀 새 컴퓨터 설치 가이드

### 1. Python 설치
```bash
python --version  # 3.10+
```

### 2. 프로젝트 복사
```bash
xcopy D:\USB\Coding\omg C:\Coding\omg /E /I /H /Y
```

### 3. 의존성 설치
```bash
cd C:\Coding\omg
pip install -r requirements.txt
```

**requirements.txt:**
```
requests>=2.28.0
pandas>=1.5.0
openpyxl>=3.0.0
python-dotenv>=0.20.0
schedule>=1.2.0
```

### 4. 환경 변수 설정

**.env 파일 생성:**
```bash
copy .env.example .env
notepad .env
```

**.env 내용:**
```
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE
```

### 5. 텔레그램 연동 확인

**telegram_notifier.py 필요:**

S12의 telegram_notifier.py를 복사:
```bash
copy C:\Coding\S12\telegram_notifier.py C:\Coding\omg\
```

또는 omg 전용으로 간단히 작성:
```python
# telegram_notifier.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    response = requests.post(url, json=data)
    return response.status_code == 200
```

### 6. 테스트 실행

**단계별 테스트:**
```bash
# 1. Universe 선정
python universe_selector.py --asset coin

# 2. Debug 파일 생성 (2-5분 소요)
python auto_debug_builder.py --limit-days 1200

# 3. Analysis Excel 생성
python coin_analysis_excel.py

# 4. 실시간 감시 시작
python crypto_realtime_monitor.py
```

### 7. Windows Task Scheduler 설정

#### 작업 1: 매일 00:10 배치 분석

1. `Win + R` → `taskschd.msc`
2. "작업 만들기"
   - 이름: `OMG_Daily_Analysis`
   - 트리거: 매일 00:10
   - 동작:
     - 프로그램: `cmd.exe`
     - 인수: `/c "C:\Coding\omg\run_daily_analysis.bat"`
     - 시작 위치: `C:\Coding\omg`

#### 작업 2: 부팅 시 실시간 감시

1. "작업 만들기"
   - 이름: `OMG_Realtime_Monitor`
   - 트리거: 컴퓨터 시작 시
   - 동작:
     - 프로그램: `python`
     - 인수: `crypto_realtime_monitor.py`
     - 시작 위치: `C:\Coding\omg`
   - 조건:
     - ❌ "AC 전원일 때만 시작" 해제
     - ❌ "배터리 사용 시 중지" 해제

---

## 📝 배치 파일 생성

### run_daily_analysis.bat
```batch
@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo OMG Daily Analysis - %date% %time%
echo ========================================

echo [1/2] Running auto_debug_builder.py...
python auto_debug_builder.py --limit-days 1200
if %ERRORLEVEL% neq 0 (
    echo ERROR: auto_debug_builder.py failed!
    exit /b 1
)

echo [2/2] Running coin_analysis_excel.py...
python coin_analysis_excel.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: coin_analysis_excel.py failed!
    exit /b 1
)

echo ========================================
echo Daily analysis completed successfully
echo ========================================
```

### run_realtime_monitor.bat
```batch
@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo OMG Realtime Monitor Starting...
echo ========================================
echo.
echo 모니터링 설정:
echo   - 체크 간격: 30분
echo   - 알림 조건: 매수선 5%% 이내
echo   - 중복 방지: 코인별/레벨별 하루 1회
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ========================================
echo.

python crypto_realtime_monitor.py

pause
```

---

## 🔧 문제 해결

### 1. crypto_realtime_monitor.py가 실행 안 됨

**원인: telegram_notifier.py 없음**

**해결:**
```bash
# S12에서 복사
copy C:\Coding\S12\telegram_notifier.py C:\Coding\omg\

# 또는 crypto_realtime_monitor.py 수정
# Line 17: from telegram_notifier import send_telegram_message
# → 직접 구현으로 변경
```

### 2. Analysis 파일을 찾을 수 없음

**원인: coin_analysis_excel.py 미실행**

**해결:**
```bash
cd C:\Coding\omg
python coin_analysis_excel.py

# output/ 폴더 확인
dir output\coin_analysis_*.xlsx
```

### 3. Debug 파일이 없음

**원인: auto_debug_builder.py 미실행**

**해결:**
```bash
cd C:\Coding\omg
python auto_debug_builder.py --limit-days 1200

# debug/ 폴더 확인
dir debug\*_debug.csv
```

### 4. 텔레그램 알림 안 옴

**원인: .env 파일 설정 오류**

**확인:**
```bash
type .env

# 토큰 테스트
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN')[:20])"
```

---

## 📊 일일 점검

### 아침 (09:00)

- [ ] 00:10 배치 분석 완료 확인
  ```bash
  dir output\coin_analysis_*.xlsx /O-D
  # 오늘 날짜 파일 있는지 확인
  ```

- [ ] 실시간 감시 실행 중 확인
  ```bash
  tasklist | findstr python
  # crypto_realtime_monitor.py 프로세스 확인
  ```

- [ ] alert_history.json 확인
  ```bash
  type alert_history.json
  # 어제 알림 내역 확인
  ```

### 저녁 (20:00)

- [ ] 오늘 받은 알림 확인
- [ ] 텔레그램 메시지 검토
- [ ] 매수 기회 있으면 분석

### 주말

- [ ] 로그 파일 정리
- [ ] 전체 백업
  ```bash
  xcopy C:\Coding\omg D:\Backup\omg_%date:~0,4%%date:~5,2%%date:~8,2% /E /I /H /Y
  ```

---

## 🎯 성능 최적화

### 30분 주기 조정

**crypto_realtime_monitor.py 수정:**
```python
# Line ~450
schedule.every(30).minutes.do(check_realtime_prices)

# 더 빠르게: 10분
schedule.every(10).minutes.do(check_realtime_prices)

# 더 느리게: 1시간
schedule.every(1).hours.do(check_realtime_prices)
```

### 알림 거리 조정

```python
# Line ~300
PROXIMITY_THRESHOLD = 5.0  # 5% → 변경 가능

# 더 빨리 알림: 10%
PROXIMITY_THRESHOLD = 10.0

# 더 늦게 알림: 2%
PROXIMITY_THRESHOLD = 2.0
```

---

## 📚 관련 문서

- **[CLAUDE.md](./CLAUDE.md)** - OMG 시스템 전체 가이드
- **[OMG_PHASE1_5_KOREAN_GUIDE.md](./OMG_PHASE1_5_KOREAN_GUIDE.md)** - Phase 1.5 전략 상세
- **[NEW_COMPUTER_SETUP.md](../NEW_COMPUTER_SETUP.md)** - 새 컴퓨터 이식 가이드
- **[REALTIME_MONITORING_SUMMARY.md](../REALTIME_MONITORING_SUMMARY.md)** - 전체 모니터링 시스템 요약

---

**문서 버전**: 1.0
**최종 수정**: 2025-11-02
**작성자**: Claude Code Assistant
