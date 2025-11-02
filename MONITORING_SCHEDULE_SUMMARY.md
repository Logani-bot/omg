# OMG 프로젝트 모니터링 스케줄 요약

## 📋 현재 실행 중인 모니터링 시스템 개요

OMG 프로젝트에는 **2개의 독립적인 모니터링 시스템**이 존재합니다:

---

## 1️⃣ 업비트 급락 감시 시스템 (`Red S/`)

### 🎯 목적
- 업비트 KRW 마켓 코인의 급격한 하락 모니터링
- 대량 하락 발생 시 즉시 알림

### ⏰ 실행 주기
- **모니터링 간격**: **1시간 단위** (매시간 정각)
- **스케줄**: `schedule.every().hour.at(":00")`
- **실행 방식**: 연속 실행 (`while True` 루프)

### 🔔 알림 조건
- **시작 알림**: -15% 이하 하락 종목이 **15개 이상** 발생 시
- **끝 알림**: 하락 종목이 **15개 미만**으로 감소 시
- **제한**: 시작 알림과 끝 알림 각각 **하루 1회**만 전송

### 📊 모니터링 대상
- 업비트 전체 KRW 마켓 코인
- 실시간 등락률 감시
- 가장 많이 하락한 상위 10개 종목 표시

### 📁 주요 파일
- `Red S/upbit_monitor.py` - 메인 모니터링 로직
- `Red S/run_monitor.py` - 실행 스크립트
- `Red S/config.json` - 설정 파일
- `Red S/alert_status.json` - 알림 상태 기록 (자동 생성)

### 🚀 실행 방법
```bash
cd "Red S"
python run_monitor.py
```

---

## 2️⃣ Envelope 근접 알림 시스템 (`Red S/envelope_alert.py`)

### 🎯 목적
- Binance 코인의 Envelope 하단선 근접 감시
- 매수 기회 포착 및 알림

### ⏰ 실행 주기
- **기본 설정**: **10분 간격** 모니터링
- **옵션**: `.env` 파일에서 `MONITOR_INTERVAL_MINUTES` 조정 가능
- **엑셀 저장**: 6회마다 (1시간마다)

### 🔔 알림 조건
- Envelope 하단선에서 **5% 이내** 근접 시 알림
- Top 30 코인 대상 (시가총액 기준)

### 📊 계산 방법
- **Envelope 기간**: 45일 이동평균
- **Envelope 폭**: ±45%
- **상단선**: MA × 1.45
- **하단선**: MA × 0.55

### 📁 주요 파일
- `Red S/envelope_alert.py` - 단일 실행 스크립트
- `Old/envelope_monitor_loop.py` - 연속 실행 버전
- `.env` - 환경 변수 (텔레그램 토큰 등)

### 🚀 실행 방법

#### 단일 실행 (수동)
```bash
python envelope_alert.py
```

#### 연속 실행 (자동)
```bash
python envelope_monitor_loop.py
```

---

## 🔄 두 시스템의 차이점

| 항목 | 업비트 급락 감시 | Envelope 근접 알림 |
|------|----------------|-------------------|
| **거래소** | 업비트 | Binance |
| **마켓** | KRW 페어 | USDT 페어 |
| **실행 주기** | 1시간 | 10분 |
| **목적** | 하락 알림 | 매수 기회 |
| **데이터 소스** | 실시간 티커 | 일봉 OHLCV |
| **알림 트리거** | -15% 이하 15개 이상 | 하단선 5% 이내 |
| **상태 관리** | 일일 1회 제한 | 연속 모니터링 |

---

## 📝 24/7 실행을 위한 권장 설정

### Windows 작업 스케줄러 설정

#### 작업 1: 업비트 급락 감시
- **트리거**: 부팅 시 + 매시간 반복
- **프로그램**: `C:\Coding\omg\Red S\run_monitor.bat`
- **조건**: 
  - ❌ "AC 전원일 때만 시작" 해제
  - ✅ "작업이 실패하면 다시 시작" (3회, 1분 간격)

#### 작업 2: Envelope 근접 알림
- **트리거**: 부팅 시 + 10분 반복
- **프로그램**: `C:\Coding\omg\Red S\run_monitor.bat` (수정 필요)
- **조건**: 위와 동일

---

## 📋 필요한 패키지

### 업비트 급락 감시
```bash
pip install requests>=2.28.0 schedule>=1.2.0
```

### Envelope 근접 알림
```bash
pip install requests pandas openpyxl python-dotenv
```

---

## 🔧 설정 파일

### Red S/config.json (업비트 급락 감시)
```json
{
  "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
  "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID_HERE",
  "decline_threshold": -15.0,
  "min_coin_count": 15,
  "check_interval_hours": 1,
  "log_level": "INFO"
}
```

### .env (Envelope 근접 알림)
```env
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID_HERE
MONITOR_INTERVAL_MINUTES=10
SAVE_EXCEL_EVERY_N_RUNS=6
```

---

## 📊 로그 및 출력

### 업비트 급락 감시
- 로그: `Red S/upbit_monitor_YYYYMMDD.log`
- 상태: `Red S/alert_status.json`

### Envelope 근접 알림
- 엑셀: `output/envelope_all_coins_YYYYMMDD_HHMMSS.xlsx`
- 알림: `output/envelope_alerts_YYYYMMDD_HHMMSS.xlsx` (있을 경우만)

---

## ⚠️ 주의사항

1. **텔레그램 토큰**: 두 시스템 모두 텔레그램 알림 사용
2. **API 제한**: 업비트/Binance API 호출 제한 주의
3. **충돌 방지**: 두 시스템을 동시 실행 가능하나, 같은 채팅 방 사용 시 알림 중복 가능
4. **24/7 실행**: 컴퓨터가 항상 켜져 있어야 함 (절전 모드 비활성화 필요)

---

## 🚀 새 컴퓨터에 설치 시 체크리스트

- [ ] Python 3.11 설치
- [ ] `Red S/` 폴더 전체 복사
- [ ] `pip install -r Red S/requirements.txt`
- [ ] `Red S/config.json` 설정 (텔레그램 토큰/채팅 ID)
- [ ] `.env` 파일 설정 (Envelope 알림용)
- [ ] Windows 작업 스케줄러 설정
- [ ] 수동 테스트 실행
- [ ] 로그 파일 확인
- [ ] 텔레그램 알림 수신 확인

---

**마지막 업데이트**: 2025-01-XX  
**작성자**: OMG Trading System


