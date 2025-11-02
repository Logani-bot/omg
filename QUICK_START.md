# OMG 시스템 빠른 시작 가이드

**Phase 1.5 암호화폐 자동 트레이딩 신호 시스템**

---

## 🚀 5분 만에 시작하기

### 1. 의존성 설치
```bash
cd C:\Coding\omg
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
copy .env.example .env
notepad .env
```

**.env 파일 내용:**
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. 텔레그램 모듈 복사
```bash
copy C:\Coding\S12\telegram_notifier.py .
```

### 4. 초기 실행 (수동)
```bash
# 00:10 자동 실행과 동일한 작업
run_daily_analysis.bat
```

**소요 시간:** 2-5분 (Top 100 코인 처리)

**생성 파일:**
- `debug/*.csv` - 100개 코인 시뮬레이션
- `output/coin_analysis_*.xlsx` - 분석 결과

### 5. 실시간 모니터링 시작
```bash
run_realtime_monitor.bat
```

---

## ⏰ 자동 실행 설정

### Windows Task Scheduler

#### 작업 1: 매일 00:10 배치 분석

1. `Win + R` → `taskschd.msc`
2. "작업 만들기"
   - **이름**: `OMG_Daily_Analysis`
   - **트리거**: 매일 00:10
   - **동작**:
     - 프로그램: `cmd.exe`
     - 인수: `/c "C:\Coding\omg\run_daily_analysis.bat"`
     - 시작: `C:\Coding\omg`

#### 작업 2: 부팅 시 실시간 감시

1. "작업 만들기"
   - **이름**: `OMG_Realtime_Monitor`
   - **트리거**: 컴퓨터 시작 시
   - **동작**:
     - 프로그램: `python`
     - 인수: `crypto_realtime_monitor.py`
     - 시작: `C:\Coding\omg`
   - **조건**: AC 전원/배터리 옵션 모두 해제

---

## 📊 시스템 동작 확인

### 배치 분석 확인
```bash
# 오늘 생성된 파일 확인
dir output\coin_analysis_*.xlsx /O-D
dir debug\*_debug.csv | find /c ".csv"
```

### 실시간 모니터링 확인
```bash
# 프로세스 확인
tasklist | findstr python

# 알림 이력 확인
type alert_history.json
```

### 로그 확인
```bash
# 배치 로그
type logs\omg_daily_%date:~0,4%%date:~5,2%%date:~8,2%.log

# 실시간 모니터 로그 (화면 출력)
```

---

## 🎯 핵심 파일

| 파일 | 용도 | 실행 주기 |
|------|------|-----------|
| **auto_debug_builder.py** | Top 100 코인 시뮬레이션 | 00:10 자동 |
| **coin_analysis_excel.py** | Analysis Excel 생성 | 00:10 자동 |
| **crypto_realtime_monitor.py** | 실시간 가격 추적 | 24/7 백그라운드 |
| **run_daily_analysis.bat** | 배치 실행 래퍼 | 스케줄러 호출 |
| **run_realtime_monitor.bat** | 모니터 실행 래퍼 | 수동/자동 시작 |

---

## 💡 일일 운영

### 아침 (09:00)
- [ ] 00:10 배치 완료 확인
- [ ] 실시간 모니터 실행 중 확인
- [ ] 텔레그램 알림 확인

### 저녁 (20:00)
- [ ] 오늘 받은 매수 알림 검토
- [ ] 매수 기회 분석

### 주말
- [ ] 로그 파일 정리 (1주일 이상)
- [ ] 전체 백업

---

## 🔧 문제 해결

### Debug 파일이 없음
```bash
python auto_debug_builder.py --limit-days 1200
```

### Analysis Excel 없음
```bash
python coin_analysis_excel.py
```

### 텔레그램 알림 안 옴
```bash
# .env 확인
type .env

# telegram_notifier.py 확인
dir telegram_notifier.py
```

### 실시간 모니터 종료됨
```bash
# 재시작
run_realtime_monitor.bat
```

---

## 📚 상세 문서

- **[OMG_COMPLETE_SYSTEM_GUIDE.md](./OMG_COMPLETE_SYSTEM_GUIDE.md)** - 전체 시스템 가이드
- **[CLAUDE.md](./CLAUDE.md)** - 개발자 문서
- **[OMG_PHASE1_5_KOREAN_GUIDE.md](./OMG_PHASE1_5_KOREAN_GUIDE.md)** - 전략 상세
- **[NEW_COMPUTER_SETUP.md](../NEW_COMPUTER_SETUP.md)** - 새 컴퓨터 이식

---

**준비 완료!** 이제 OMG 시스템이 자동으로 작동합니다. 🎉
