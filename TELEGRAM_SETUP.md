# 텔레그램 알림 설정 가이드

## 1. 텔레그램 봇 만들기

### 1.1 BotFather와 대화하기
1. 텔레그램에서 `@BotFather`를 검색
2. `/newbot` 명령어 입력
3. 봇 이름 입력 (예: `OMG Envelope Alert`)
4. 봇 유저네임 입력 (예: `omg_envelope_bot`, 반드시 `bot`으로 끝나야 함)
5. **봇 토큰**을 복사해 두세요 (예: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 1.2 봇 설정
1. `/setdescription` - 봇 설명 설정 (선택사항)
2. `/setcommands` - 봇 명령어 설정 (선택사항)

## 2. Chat ID 알아내기

### 방법 1: 개인 채팅 (권장)
1. 위에서 만든 봇을 검색하여 대화 시작
2. 아무 메시지나 보내기 (예: `/start`)
3. 브라우저에서 다음 URL 접속:
   ```
   https://api.telegram.org/bot<봇토큰>/getUpdates
   ```
4. JSON 응답에서 `"chat":{"id":123456789}` 찾기
5. 이 숫자가 **Chat ID**입니다

### 방법 2: 그룹 채팅
1. 그룹을 만들고 봇을 초대
2. 그룹에서 아무 메시지나 보내기
3. 위와 동일한 URL로 `getUpdates` 호출
4. Chat ID는 음수로 표시됨 (예: `-123456789`)

## 3. .env 파일 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 입력:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

- `TELEGRAM_BOT_TOKEN`: BotFather에서 받은 봇 토큰
- `TELEGRAM_CHAT_ID`: 위에서 확인한 Chat ID

**주의**: `.env` 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다.

## 4. 테스트

다음 명령어로 알림이 정상 작동하는지 확인:

```bash
python envelope_alert.py
```

- **알림 대상 코인이 있으면**: 텔레그램으로 메시지가 전송됩니다
- **알림 대상 코인이 없으면**: "알림 대상 코인이 없어 텔레그램 메시지를 보내지 않습니다" 메시지가 출력됩니다
- **.env 파일이 없으면**: "텔레그램 설정이 없습니다. .env 파일을 확인하세요" 메시지가 출력됩니다

## 5. 알림 예시

텔레그램으로 다음과 같은 형식의 메시지가 전송됩니다:

```
🚨 Envelope 하단선 근접 알림 🚨

📊 총 3개 코인이 하단선 5% 이내 접근
⏰ 2025-10-12 03:15:30
━━━━━━━━━━━━━━━━━━━━

1. Ethereum (ETH)
   💰 현재가: $2,456.7800
   📉 하단선: $2,380.5600
   📏 이격도: 3.20%

2. Cardano (ADA)
   💰 현재가: $0.3521
   📉 하단선: $0.3450
   📏 이격도: 2.06%

3. Polkadot (DOT)
   💰 현재가: $4.1250
   📉 하단선: $4.0800
   📏 이격도: 1.10%
```

## 6. 문제 해결

### 봇이 메시지를 보내지 않아요
- `.env` 파일이 프로젝트 루트에 있는지 확인
- 봇 토큰과 Chat ID가 올바른지 확인
- 봇과 대화를 시작했는지 확인 (최소 1회 메시지 전송 필요)

### "Chat not found" 에러
- Chat ID가 올바른지 다시 확인
- 봇과 대화를 시작했는지 확인

### "Unauthorized" 에러
- 봇 토큰이 올바른지 확인
- BotFather에서 봇이 삭제되지 않았는지 확인

## 7. 자동 실행 (선택사항)

### Windows 작업 스케줄러
1. `작업 스케줄러` 실행
2. `기본 작업 만들기` 클릭
3. 트리거: 매일 특정 시간 또는 반복 실행
4. 작업: 프로그램 시작
   - 프로그램: `python`
   - 인수: `c:\Coding\OMG\envelope_alert.py`
   - 시작 위치: `c:\Coding\OMG`

### Linux/Mac Cron
```bash
# 매 시간 정각에 실행
0 * * * * cd /path/to/OMG && python envelope_alert.py

# 매일 오전 9시와 오후 6시에 실행
0 9,18 * * * cd /path/to/OMG && python envelope_alert.py
```

---

문제가 있으면 [이슈](https://github.com/your-repo/issues)를 남겨주세요!

