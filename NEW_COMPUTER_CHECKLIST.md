# OMG 시스템 - 새 컴퓨터 이식 체크리스트

**빠른 이식 가이드 (10분 완료)**

---

## ✅ 사전 준비 (기존 컴퓨터)

### 1. Git에 푸시
```bash
cd C:\Coding\omg
git init
git add .
git commit -m "OMG Phase 1.5 complete system"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. 텔레그램 정보 메모
- [ ] TELEGRAM_BOT_TOKEN 복사
- [ ] TELEGRAM_CHAT_ID 복사

---

## 🚀 새 컴퓨터 설치 (순서대로)

### Step 1: Python 설치
```bash
# https://www.python.org/downloads/
python --version
# 출력: Python 3.10 이상
```

**중요:** ✅ "Add Python to PATH" 체크!

### Step 2: Git Clone
```bash
cd C:\Coding
git clone <your-omg-repo-url> omg
cd omg
```

### Step 3: 의존성 설치
```bash
pip install -r requirements.txt
```

**예상 시간:** 1-2분

### Step 4: 환경 변수 설정
```bash
copy .env.example .env
notepad .env
```

**.env 파일 내용:**
```
TELEGRAM_BOT_TOKEN=기존_컴퓨터에서_복사한_토큰
TELEGRAM_CHAT_ID=기존_컴퓨터에서_복사한_ID
```

### Step 5: telegram_notifier.py 준비

**옵션 A: S12가 있다면**
```bash
copy C:\Coding\S12\telegram_notifier.py .
```

**옵션 B: 직접 생성**
```bash
notepad telegram_notifier.py
```

**내용:**
```python
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

### Step 6: 초기 실행 테스트
```bash
# 텔레그램 연결 테스트
python -c "from telegram_notifier import send_telegram_message; send_telegram_message('✅ OMG 시스템 설치 완료')"
```

텔레그램에 메시지 오면 성공! ✅

### Step 7: 배치 분석 실행 (첫 실행)
```bash
run_daily_analysis.bat
```

**예상 시간:** 2-5분 (Top 100 코인 처리)

**확인:**
- [ ] `debug/*.csv` 파일 100개 생성
- [ ] `output/coin_analysis_*.xlsx` 파일 생성

### Step 8: 실시간 감시 시작
```bash
run_realtime_monitor.bat
```

**확인:**
- [ ] "OMG 실시간 암호화폐 모니터링 시작" 메시지
- [ ] 에러 없이 대기 중

---

## ⏰ Windows Task Scheduler 설정

### 작업 1: 매일 00:10 배치 분석

1. `Win + R` → `taskschd.msc`
2. "작업 만들기"

**일반 탭:**
- 이름: `OMG_Daily_Analysis`
- 설명: `매일 00:10 Top 100 코인 분석`

**트리거 탭:**
- 새로 만들기
- 작업 시작: `일정에 따라`
- 설정: `매일`
- 시작: `00:10:00`
- ✅ 사용함

**동작 탭:**
- 새로 만들기
- 동작: `프로그램 시작`
- 프로그램/스크립트: `cmd.exe`
- 인수 추가: `/c "C:\Coding\omg\run_daily_analysis.bat"`
- 시작 위치: `C:\Coding\omg`

**조건 탭:**
- ❌ "컴퓨터의 AC 전원이 켜져 있을 때만 작업 시작" 체크 해제
- ❌ "컴퓨터가 배터리 전원을 사용할 때 중지" 체크 해제

**설정 탭:**
- ✅ "작업이 요청 시 실행되도록 허용"
- ✅ "예약된 시작 시간을 놓친 경우 즉시 작업 시작"

### 작업 2: 부팅 시 실시간 감시

**일반 탭:**
- 이름: `OMG_Realtime_Monitor`
- 설명: `24/7 실시간 매수 기회 감시`

**트리거 탭:**
- 새로 만들기
- 작업 시작: `시작할 때`
- ✅ 사용함

**동작 탭:**
- 프로그램/스크립트: `python`
- 인수 추가: `crypto_realtime_monitor.py`
- 시작 위치: `C:\Coding\omg`

**조건 탭:**
- ❌ AC 전원 체크 해제
- ❌ 배터리 중지 체크 해제

---

## 🧪 최종 테스트

### 1. 배치 분석 수동 실행
```bash
cd C:\Coding\omg
run_daily_analysis.bat
```

**확인:**
- [ ] 에러 없이 완료
- [ ] `debug/*.csv` 100개
- [ ] `output/coin_analysis_*.xlsx` 생성
- [ ] `logs/omg_daily_*.log` 생성

### 2. 실시간 감시 수동 실행
```bash
run_realtime_monitor.bat
```

**확인:**
- [ ] "모니터링 시작" 메시지
- [ ] 30분 후 체크 메시지
- [ ] 에러 없음

### 3. 스케줄러 작업 실행 테스트

**작업 스케줄러에서:**
1. `OMG_Daily_Analysis` 우클릭 → "실행"
2. "마지막 실행 결과" 확인 → `0x0` (성공)

3. `OMG_Realtime_Monitor` 우클릭 → "실행"
4. Task Manager에서 `python.exe` 확인

### 4. 컴퓨터 재부팅 테스트

**재부팅 후:**
- [ ] `OMG_Realtime_Monitor` 자동 시작 확인
  ```bash
  tasklist | findstr python
  ```

---

## 📊 일일 점검

### 아침 (09:00)

**배치 분석 확인:**
```bash
dir output\coin_analysis_*.xlsx /O-D
# 오늘 날짜 파일 있는지
```

**실시간 감시 확인:**
```bash
tasklist | findstr python
# crypto_realtime_monitor.py 실행 중인지
```

**로그 확인:**
```bash
type logs\omg_daily_%date:~0,4%%date:~5,2%%date:~8,2%.log
```

### 저녁 (20:00)

- [ ] 오늘 받은 텔레그램 알림 확인
- [ ] 매수 기회 있으면 분석

---

## 🔧 문제 해결

### "ModuleNotFoundError: No module named 'xxx'"
```bash
pip install -r requirements.txt
```

### 텔레그램 메시지 안 옴
```bash
# .env 확인
type .env

# 토큰 테스트
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN')[:20])"
```

### telegram_notifier.py 없음
```bash
# S12에서 복사 또는 직접 생성 (위 Step 5 참고)
```

### Debug 파일 없음
```bash
python auto_debug_builder.py --limit-days 1200
```

### Analysis Excel 없음
```bash
python coin_analysis_excel.py
```

### 스케줄러 작업이 실행 안 됨
- Python 경로 확인: `where python`
- 배치 파일 경로 확인
- "마지막 실행 결과" 코드 확인 (0x0 = 성공)

---

## ✅ 완료 체크리스트

- [ ] Python 3.10+ 설치
- [ ] Git clone 완료
- [ ] pip install 완료
- [ ] .env 파일 설정
- [ ] telegram_notifier.py 준비
- [ ] 텔레그램 연결 테스트 성공
- [ ] 배치 분석 1회 실행 성공
- [ ] 실시간 감시 시작 성공
- [ ] Windows Task Scheduler 2개 작업 등록
- [ ] 스케줄러 작업 수동 실행 테스트
- [ ] 재부팅 후 자동 시작 확인

---

## 🎉 완료!

모든 체크리스트 완료 시 OMG 시스템이 새 컴퓨터에서 정상 작동합니다!

**자동 실행 확인:**
- 매일 00:10 → 자동 배치 분석
- 부팅 시 → 실시간 감시 자동 시작
- 매수 기회 → 텔레그램 자동 알림

---

**소요 시간:** 전체 약 10-15분
**난이도:** ⭐⭐☆☆☆ (쉬움)
