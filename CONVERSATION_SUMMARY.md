# 개발 대화 요약 (2025-10-12)

## 🎯 프로젝트 개요
OMG 암호화폐 분석 및 알림 시스템

---

## 📂 주요 파일

### 1. **envelope_alert.py**
- **역할**: Envelope 하단선 근접 알림 (단일 실행)
- **기능**:
  - 45일 이동평균 기준 Envelope 계산
  - 이격도 5% 이내 코인 감지
  - 텔레그램 알림 전송
  - 엑셀 파일 저장 (전체 코인 + 알림 대상)
- **실행**: `python envelope_alert.py`

### 2. **envelope_monitor_loop.py**
- **역할**: 연속 모니터링 버전
- **기능**: 설정된 간격(기본 10분)마다 자동 체크
- **실행**: `python envelope_monitor_loop.py`
- **주의**: 컴퓨터 켜놓아야 함

### 3. **run_envelope_alert.bat**
- **역할**: Windows 작업 스케줄러용 배치 파일
- **사용**: 작업 스케줄러에 등록하여 자동 실행

### 4. **coin_analysis_excel.py**
- **역할**: Top50 코인 분석 엑셀 생성
- **기능**:
  - 시가총액 Top 50 코인
  - H값 기준 매수선 계산 (44%, 48%, 54%, 59%, 65%, 72%, 79%)
  - 현재가와 매수선 거리(%) 계산
  - 동적 소수점 포맷팅 (H값 기준)
- **실행**: `python coin_analysis_excel.py`

### 5. **auto_debug_builder.py**
- **역할**: Top100 코인 debug 파일 생성
- **기능**:
  - Binance API에서 OHLCV 데이터 수집
  - Phase 1.5 시뮬레이션 실행
  - 각 코인별 `{SYMBOL}_debug.csv` 생성
- **실행**: `python auto_debug_builder.py`

### 6. **universe_selector.py**
- **역할**: 코인 리스트 관리
- **기능**:
  - CoinGecko API로 Top100 코인 수집
  - 래핑/브릿지 토큰 제외
  - `top_list_coin.csv` 저장

---

## ⚙️ 설정 파일

### **.env** (직접 생성 필요)
```bash
# 텔레그램 봇 설정
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# 모니터링 간격 (선택사항)
MONITOR_INTERVAL_MINUTES=10
SAVE_EXCEL_EVERY_N_RUNS=6
```

---

## 🔧 주요 수정 사항

### 1. **Envelope 계산**
- 기간: 45일 이동평균
- Alpha: 45% (상단선 +45%, 하단선 -45%)
- 근접 기준: 5% 이내

### 2. **동적 소수점 포맷팅**
- H ≤ 1: 소수점 6자리
- 1 < H ≤ 10: 소수점 4자리
- H > 10: 소수점 2자리

### 3. **텔레그램 메시지 형식**
```
🚨 Red S 근접 알림 🚨
━━━━━━━━━━━━━━━━━━━━

1. Ethereum (ETH)
   - 현재가: $2,456.7800
   - 하단선: $2,380.5600
   - 이격도: 3.20%
```

### 4. **제외 토큰**
- 스테이블코인: USDT, USDC, DAI 등
- 래핑 토큰: WBTC, WETH, STETH 등
- API 미지원: HYPE, LEO, FIGR_HELOC 등

---

## 🚀 실행 순서

### 일일 분석 워크플로우
```bash
# 1. Top100 코인 리스트 업데이트
python universe_selector.py

# 2. Debug 파일 생성 (1200일 데이터)
python auto_debug_builder.py

# 3. 코인 분석 엑셀 생성
python coin_analysis_excel.py

# 4. Envelope 알림 체크
python envelope_alert.py
```

### 자동 모니터링
- **작업 스케줄러**: `SCHEDULER_SETUP.md` 참고
- **연속 실행**: `python envelope_monitor_loop.py`

---

## 📊 출력 파일

### output/ 폴더
- `coin_analysis_YYYYMMDD_HHMMSS.xlsx` - 코인 분석 결과
- `envelope_all_coins_YYYYMMDD_HHMMSS.xlsx` - 전체 코인 Envelope 데이터
- `envelope_alerts_YYYYMMDD_HHMMSS.xlsx` - 알림 대상 코인 (있을 경우)

### data/ 폴러
- `{SYMBOL}_debug.csv` - 각 코인별 Phase 1.5 시뮬레이션 결과
- `top_list_coin.csv` - Top100 코인 리스트

---

## 🐛 주요 해결한 이슈

1. **H값 갱신 문제**: 고점 기준 H값 동적 갱신 로직 추가
2. **2025-10-09 저가 데이터 오류**: 해당 날짜 저가를 종가로 대체
3. **텔레그램 메시지 포맷**: Unicode 문자 제거, HTML 포맷 적용
4. **소수점 표시**: 가격 크기에 따른 동적 포맷팅
5. **퍼센트 표시**: 엑셀에서 자동 % 포맷 적용

---

## 📚 참고 문서

- `README.md` - 프로젝트 전체 설명
- `TELEGRAM_SETUP.md` - 텔레그램 봇 설정 가이드
- `SCHEDULER_SETUP.md` - Windows 작업 스케줄러 설정
- `.env.example` - 환경 변수 예시

---

## 💡 추가 개선 아이디어

- [ ] 클라우드 서버 배포 (AWS Lambda, GCP Cloud Functions)
- [ ] 디스코드 웹훅 지원
- [ ] 이메일 알림 추가
- [ ] 알림 이력 DB 저장
- [ ] 웹 대시보드 구현
- [ ] 백테스팅 결과 시각화

---

## 🔗 외부 API

- **CoinGecko**: 시가총액, 현재가, 24시간 변동률
- **Binance**: 일봉 OHLCV 데이터
- **Telegram Bot API**: 알림 메시지 전송

---

**마지막 업데이트**: 2025-10-12  
**개발 환경**: Windows 10, Python 3.x, Cursor IDE

