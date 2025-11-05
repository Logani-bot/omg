# Slack 알림 설정 가이드

## 개요

OMG 암호화폐 모니터링 시스템에서 텔레그램 알림과 함께 Slack 알림을 받을 수 있습니다.
Slack 알림은 **선택사항**이며, 설정하지 않아도 텔레그램 알림은 정상적으로 작동합니다.

---

## 1. Slack Webhook URL 얻기

### 1.1 Slack 워크스페이스 준비

1. **Slack 워크스페이스에 로그인**
   - 개인 워크스페이스 또는 팀 워크스페이스 사용 가능
   - 워크스페이스가 없으면 [Slack 워크스페이스 만들기](https://slack.com/create)에서 생성

### 1.2 Incoming Webhooks 앱 추가

1. **Slack 워크스페이스에서 앱 추가**
   - 왼쪽 사이드바에서 **"앱"** 또는 **"Apps"** 클릭
   - 또는 [Slack 앱 디렉토리](https://slack.com/apps) 접속

2. **Incoming Webhooks 검색**
   - 검색창에 `Incoming Webhooks` 입력
   - **"Incoming Webhooks"** 앱 선택

3. **앱 추가**
   - **"앱 추가"** 또는 **"Add to Slack"** 버튼 클릭
   - 워크스페이스 선택 (이미 로그인되어 있으면 자동 선택)

### 1.3 Webhook URL 생성

1. **알림을 받을 채널 선택**
   - 드롭다운에서 채널 선택 (예: `#crypto-alerts`, `#general`, `#알림`)
   - 또는 **"새 채널 만들기"**로 새 채널 생성 가능

2. **Webhook URL 생성**
   - **"Incoming Webhook 추가"** 또는 **"Add Incoming Webhooks integration"** 클릭
   - 생성된 **Webhook URL** 복사
     - 예: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL/HERE`

3. **설정 저장** (선택사항)
   - Webhook 이름: `OMG Crypto Alerts` (원하는 이름으로 변경 가능)
   - 설명: `암호화폐 매수 목표 접근 알림` (선택사항)
   - **"설정 저장"** 클릭

---

## 2. .env 파일에 Webhook URL 추가

### 2.1 .env 파일 위치 확인

`.env` 파일은 프로젝트 루트 디렉토리에 있습니다:
```
C:\Users\log\Desktop\CODE\OMG\.env
```

### 2.2 .env 파일 편집

1. **텍스트 에디터로 .env 파일 열기**
   - 메모장, VS Code, 또는 아무 텍스트 에디터 사용

2. **Slack Webhook URL 추가**
   - 파일 끝에 다음 줄 추가:

```env
# Slack Webhook (선택사항)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

3. **실제 URL로 교체**
   - 위에서 복사한 Webhook URL로 `YOUR/WEBHOOK/URL` 부분을 교체
   - 예시:
     ```env
     SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL/HERE
     ```

4. **파일 저장**

### 2.3 .env 파일 예시

전체 `.env` 파일 예시:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

# Telegram Chat IDs
TELEGRAM_CHAT_ID_ME=YOUR_CHAT_ID
TELEGRAM_CHAT_ID_YOONJOO=YOUR_CHAT_ID
TELEGRAM_CHAT_ID_MINJEONG=YOUR_CHAT_ID
TELEGRAM_CHAT_ID_JUMEONI=YOUR_CHAT_ID

# Slack Webhook (선택사항)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL/HERE
```

**주의**: 
- `.env` 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다.
- Webhook URL은 **비밀 정보**이므로 절대 공개하지 마세요.

---

## 3. 테스트

### 3.1 Slack 메시지 전송 테스트

다음 명령어로 Slack 알림이 정상 작동하는지 확인:

```bash
cd C:\Users\log\Desktop\CODE\OMG
python slack_notifier.py
```

**예상 결과:**
- ✅ **성공**: Slack 채널에 "🤖 *Slack 봇 테스트*" 메시지가 표시됨
- ❌ **실패**: "Slack Webhook URL이 설정되지 않았습니다." 메시지 출력

### 3.2 실제 모니터링 시스템 테스트

실제 모니터링 시스템에서 Slack 알림이 작동하는지 확인:

```bash
python crypto_realtime_monitor.py
```

알림이 발생하면:
- 텔레그램 알림과 **동시에** Slack 알림도 전송됩니다
- 콘솔에 `알람 전송 성공: ETH B1 (텔레그램, Slack)` 같은 메시지가 표시됩니다

---

## 4. 알림 예시

Slack에서 다음과 같은 형식의 메시지를 받게 됩니다:

### 매수 목표 접근 알림

```
🪙 *매수 목표 접근 알림*
────────────
코인명: Ethereum (ETH)
시총 순위: 2

현재가: $2,456.7800
매수목표: *B1 - $2,380.5600*
이격도: *3.20%*
────────────
_* 기준 고점: $2,500.0000_
```

### 매수 실행 알림

```
⚡ *매수 실행 알림*
────────────
코인명: Ethereum (ETH)
시총 순위: 2

매수 목표: B1 — $2,380.56
5분봉 저가: $2,375.00

현재가: $2,380.00
평균매수가: $2,380.56
예상 매도가: $2,564.00 (+7.7%)
────────────
_* 기준 고점: $2,500.00_
```

---

## 5. 문제 해결

### Slack에서 메시지를 받지 못해요

1. **Webhook URL 확인**
   - `.env` 파일의 `SLACK_WEBHOOK_URL`이 올바른지 확인
   - URL이 완전히 복사되었는지 확인 (끝 부분이 잘리지 않았는지)

2. **Webhook 활성화 확인**
   - Slack 워크스페이스에서 Incoming Webhooks 앱이 활성화되어 있는지 확인
   - Webhook이 삭제되지 않았는지 확인

3. **채널 확인**
   - Webhook이 연결된 채널에 접근 권한이 있는지 확인
   - 채널이 아카이브되지 않았는지 확인

### "Slack Webhook URL이 설정되지 않았습니다" 메시지가 나와요

1. **.env 파일 위치 확인**
   - `.env` 파일이 `crypto_realtime_monitor.py`와 같은 디렉토리에 있는지 확인

2. **환경 변수 형식 확인**
   - `.env` 파일에서 `SLACK_WEBHOOK_URL=https://...` 형식이 올바른지 확인
   - 등호(`=`) 앞뒤에 공백이 없는지 확인

3. **Python 재시작**
   - `.env` 파일을 수정한 후 Python 스크립트를 재시작해야 합니다

### Slack 알림은 안 되는데 텔레그램은 되요

- **정상입니다!** Slack 알림은 선택사항입니다.
- 텔레그램 알림이 정상 작동하면 시스템은 정상입니다.
- Slack 알림을 원하면 위의 설정을 따라하세요.

### Webhook URL을 변경하고 싶어요

1. Slack에서 기존 Webhook 삭제 (선택사항)
2. 새로운 Webhook URL 생성 (위 1.3 단계 참조)
3. `.env` 파일의 `SLACK_WEBHOOK_URL` 업데이트
4. Python 스크립트 재시작

---

## 6. Slack 알림 비활성화

Slack 알림을 받고 싶지 않으면:

1. **.env 파일에서 삭제**
   - `SLACK_WEBHOOK_URL=...` 줄을 삭제하거나 주석 처리
   - 또는 해당 줄을 삭제

2. **Python 스크립트 재시작**

이렇게 하면 텔레그램 알림만 전송됩니다.

---

## 7. 보안 주의사항

⚠️ **중요**: Webhook URL은 누구나 메시지를 보낼 수 있는 URL입니다.

1. **Webhook URL 공개 금지**
   - GitHub, GitLab 등 공개 저장소에 커밋하지 마세요
   - `.env` 파일은 이미 `.gitignore`에 포함되어 있습니다

2. **Webhook URL 유출 시**
   - 즉시 Slack에서 Webhook 삭제
   - 새로운 Webhook URL 생성
   - `.env` 파일 업데이트

3. **Webhook URL 보관**
   - 비밀번호 관리자에 저장하는 것을 권장합니다
   - 여러 사람과 공유할 때는 안전한 방법으로 전달하세요

---

## 8. 추가 정보

### Slack 알림 vs 텔레그램 알림

- **텔레그램**: HTML 형식 지원, 개인 채팅 가능
- **Slack**: 마크다운 형식, 팀 채널 공유 가능

두 알림은 **동일한 내용**을 전송하지만, 각 플랫폼에 맞게 포맷팅됩니다.

### 여러 Slack 채널에 알림 보내기

여러 채널에 알림을 보내려면:
1. 각 채널마다 별도의 Webhook URL 생성
2. 코드 수정이 필요합니다 (현재는 하나의 Webhook만 지원)

---

## 도움말

문제가 있으면:
1. 위의 "문제 해결" 섹션 확인
2. 콘솔 로그 확인 (에러 메시지 확인)
3. Slack Webhook 설정 페이지에서 Webhook 상태 확인

---

**설정 완료 후**: `python crypto_realtime_monitor.py`를 실행하여 모니터링 시스템을 시작하세요!


