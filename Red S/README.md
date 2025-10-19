# 업비트 코인 모니터링 시스템

업비트 API를 사용하여 코인 등락률을 모니터링하고, 특정 조건에 따라 텔레그램 알림을 보내는 시스템입니다.

## 주요 기능

- **1시간 단위 모니터링**: 매시간 정각에 업비트 코인 등락률 확인
- **급락 알림**: -15% 이하 하락 종목이 15개 이상일 때 텔레그램 알림
- **하루 최대 1회 알림**: 시작 알림과 끝 알림을 하루에 최대 한 번씩만 전송
- **상세 정보 제공**: 하락 종목의 이름, 가격, 등락률 등 상세 정보 포함

## 설치 및 설정

### 1. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 텔레그램 봇 설정

1. 텔레그램에서 [@BotFather](https://t.me/botfather)와 대화
2. `/newbot` 명령어로 새 봇 생성
3. 봇 이름과 사용자명 설정
4. 발급받은 토큰을 `config.json`에 입력

### 3. 채팅 ID 확인

1. 생성한 봇과 대화 시작
2. [@userinfobot](https://t.me/userinfobot)에게 메시지 전송
3. 받은 Chat ID를 `config.json`에 입력

### 4. 설정 파일 수정

`config.json` 파일을 열어서 다음 정보를 입력하세요:

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

## 사용 방법

### 테스트 실행

```bash
python run_test.py
```

### 연결 테스트

```bash
python test_connection.py
```

### 정식 실행

```bash
python run_monitor.py
```

## 파일 구조

```
Red S/
├── upbit_monitor.py          # 메인 모니터링 시스템
├── telegram_notifier.py      # 텔레그램 알림 기능
├── config.json              # 설정 파일
├── requirements.txt         # 필요한 패키지 목록
├── run_monitor.py          # 정식 실행 스크립트
├── run_test.py             # 테스트 실행 스크립트
├── test_connection.py      # 연결 테스트 스크립트
├── alert_status.json       # 알림 상태 저장 파일 (자동 생성)
├── upbit_monitor_YYYYMMDD.log  # 로그 파일 (자동 생성)
└── README.md               # 이 파일
```

## 알림 조건

### 시작 알림
- -15% 이하 하락 종목이 15개 이상
- 해당 날짜에 아직 시작 알림을 보내지 않음

### 끝 알림
- -15% 이하 하락 종목이 15개 미만
- 해당 날짜에 시작 알림은 보냈지만 끝 알림은 보내지 않음

### 알림 제한
- 시작 알림과 끝 알림은 각각 하루에 최대 1회만 전송
- 끝 알림에는 추가 안내 메시지 포함

## 로그 확인

시스템 실행 중 생성되는 로그 파일을 확인하여 모니터링 상태를 파악할 수 있습니다:

```
upbit_monitor_YYYYMMDD.log
```

## 주의사항

1. **API 제한**: 업비트 API는 호출 제한이 있으므로 과도한 요청을 피해주세요.
2. **보안**: API 키와 텔레그램 토큰은 외부에 노출되지 않도록 주의하세요.
3. **투자 주의**: 이 시스템은 참고용이며, 투자 결정은 신중하게 하시기 바랍니다.

## 문제 해결

### 텔레그램 연결 실패
- 봇 토큰과 채팅 ID가 올바른지 확인
- 봇과 대화를 시작했는지 확인

### API 오류
- 인터넷 연결 상태 확인
- 업비트 API 서버 상태 확인

### 로그 확인
- 로그 파일에서 상세한 오류 메시지 확인

