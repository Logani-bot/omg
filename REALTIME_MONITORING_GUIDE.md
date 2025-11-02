# 실시간 모니터링 가이드

## 📊 현재 상태 vs 실시간 감시 비교

### 현재 방식 (폴링)
- **Envelope 알림**: 10분 간격
- **업비트 급락**: 1시간 간격
- **방식**: REST API 폴링

### 실시간 감시 방식
- **WebSocket**: 즉시 업데이트 (연결 유지)
- **장점**: 최소한의 지연, 즉각적인 알림
- **단점**: 연결 관리 복잡, 리소스 사용

---

## ⚖️ 10분 주기 vs 실시간 비교

### 📊 성능 및 리소스

| 항목 | 10분 폴링 | 실시간 WebSocket |
|------|----------|-----------------|
| **API 호출** | 144회/일 | 1회 연결 + 유지 |
| **서버 부하** | 중간 | 높음 (연결 유지) |
| **CPU/메모리** | 낮음 | 높음 |
| **네트워크** | 간헐적 | 지속적 |
| **지연 시간** | 0-10분 | 0-1초 |
| **구현 복잡도** | 낮음 | 높음 |

### 💰 API 비용
- **업비트 폴링**: 무료 (1분당 30회 제한)
- **Binance 폴링**: 무료
- **WebSocket**: 무료 (연결 유지 비용만)

### 🔔 알림 빈도
- **10분**: 하루 최대 144회 체크, 알림은 조건 충족 시만
- **실시간**: 초당 수십 개 업데이트 가능

---

## 🎯 실시간 감시가 필요한 경우

### ✅ 실시간이 적합한 경우
1. **고빈도 트레이딩**: 초단위 매수/매도 결정
2. **러시아워 감시**: 시장 급변 시기
3. **포지션 청산**: 손절선 근접 시 즉시 대응
4. **스캘핑**: 초단위 차익거래

### ❌ 폴링이 적합한 경우
1. **중장기 투자**: 일봉/주봉 기반 전략
2. **엔벨로프 전략**: 장기 추세에 따른 매수
3. **24/7 자동화**: 안정적이고 장기 운용
4. **리소스 절약**: 저사양 서버/PC

---

## 🔍 현재 OMG 시스템 분석

### Envelope 근접 알림 (10분)
```
목적: 매수 기회 포착
데이터: 일봉 OHLCV (Binance)
기준: 45일 MA ± 45%
알림: 하단선 5% 이내

→ 일봉 기반이므로 실시간 불필요
→ 10분 주기로 충분함 (변동 크지 않음)
```

### 업비트 급락 감시 (1시간)
```
목적: 대량 하락 포착
데이터: 실시간 티커 (업비트)
기준: -15% 이상 하락 15개 이상
알림: 일일 1회 제한

→ 1시간이면 충분 (급락은 금방 사라지지 않음)
→ 실시간으로 줄여도 효과 제한적
```

---

## 🚀 주기 최적화 방안

### 옵션 1: 현재 유지 (권장)
```python
# Envelope: 10분
# 업비트: 1시간
# 이유: 리소스 효율, 알림 스팸 방지
```

### 옵션 2: 동적 주기 조정
```python
# Envelope: 가까워질수록 빨리 체크
if distance_pct <= 1.0:    # 1% 이내
    interval = 60           # 1분
elif distance_pct <= 3.0:  # 3% 이내
    interval = 180          # 3분
elif distance_pct <= 10.0: # 10% 이내
    interval = 600          # 10분
else:
    interval = 1800         # 30분
```

### 옵션 3: WebSocket 실시간 (복잡)
```python
# WebSocket 연결 유지
# 구현 비용 높음, 추가 패키지 필요
# websocket-client, ccxt 등
```

---

## 💻 구현 복잡도 비교

### 현재 방식 (폴링) - 간단
```python
# 단순 반복 체크
while True:
    check_conditions()
    time.sleep(600)  # 10분
```

### 동적 주기 - 중간
```python
# 거리에 따라 주기 변경
while True:
    distance = calculate_distance()
    interval = get_optimal_interval(distance)
    check_conditions()
    time.sleep(interval)
```

### WebSocket 실시간 - 복잡
```python
# WebSocket 연결 관리
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    check_and_alert(data)

ws = websocket.WebSocketApp(
    "wss://api.binance.com/stream?streams=btcusdt@ticker",
    on_message=on_message
)
ws.run_forever()

# + 재연결 로직
# + 에러 처리
# + 멀티 심볼 관리
```

---

## 📈 추천 전략

### 🥇 권장: 현재 유지 + 동적 조정
```python
"""
현재: 10분 고정
개선: 거리 기반 동적 조정

장점:
- 구현 간단 (기존 코드 수정만)
- 리소스 효율
- 알림 정확도 향상
- 스팸 방지
"""

def get_optimal_interval(current_price, target_price):
    """거리에 따라 최적 주기 계산"""
    distance_pct = abs((current_price - target_price) / target_price * 100)
    
    if distance_pct <= 1.0:
        return 60   # 1분 - 매우 근접
    elif distance_pct <= 3.0:
        return 180  # 3분 - 근접
    elif distance_pct <= 10.0:
        return 600  # 10분 - 접근
    else:
        return 1800 # 30분 - 멀리
```

### 🥈 대안: WebSocket (고급)
```
필요한 경우:
- 초단위 차익거래
- 고빈도 알림 필수
- 투자 규모가 크고 매수 타이밍 중요

필요 패키지:
- websocket-client
- websockets
- ccxt (선택)

추가 작업:
- 연결 관리 코드
- 재연결 로직
- 멀티 심볼 처리
- 에러 핸들링
```

---

## 🎯 결론 및 권장사항

### ✅ 현재 10분 주기 권장 이유

1. **리소스 효율**: CPU/메모리/네트워크 절약
2. **안정성**: 장기 실행에 안정적
3. **스팸 방지**: 과도한 알림 방지
4. **구현 간단**: 유지보수 쉬움
5. **충분한 감지**: 일봉 기반 전략에 적합

### 🔧 가능한 개선

1. **동적 주기**: 거리 기반 자동 조정
2. **우선순위**: 중요한 코인 더 자주 체크
3. **시간대 최적화**: 장중 더 자주, 야간 덜 자주

### 🚫 실시간 WebSocket 비권장

**이유:**
- Envelope 전략은 일봉 기반 (실시간 불필요)
- 구현 복잡도 높음
- 리소스 소모 큼
- 알림 스팸 위험
- 현재 전략에 과도한 투자

---

## 📝 구현 예시 (동적 주기)

```python
# c:\Coding\omg\Red S\envelope_monitor_smart.py

import time
import os
from datetime import datetime
from dotenv import load_dotenv

from envelope_alert import AlertMonitor, send_telegram_message

load_dotenv()

class SmartEnvelopeMonitor:
    """동적 주기 Envelope 모니터"""
    
    def get_optimal_interval(self, alerts, all_data):
        """알림 거리에 따라 최적 주기 계산"""
        if not alerts:
            return 1800  # 30분 (알림 없음)
        
        # 가장 가까운 코인 찾기
        min_distance = min(alert.get('이격도(%)', 99) for alert in alerts)
        
        if min_distance <= 1.0:
            return 60   # 1분 - 매우 위험
        elif min_distance <= 3.0:
            return 180  # 3분 - 주의
        elif min_distance <= 5.0:
            return 300  # 5분 - 관심
        elif min_distance <= 10.0:
            return 600  # 10분 - 감시
        else:
            return 1800 # 30분 - 여유
    
    def run_smart_monitoring(self):
        """스마트 모니터링 실행"""
        print("="*60)
        print("Smart Envelope Monitor - 동적 주기 모니터링")
        print("="*60)
        
        while True:
            try:
                # 체크
                monitor = AlertMonitor()
                alerts, all_data = monitor.monitor_all_coins()
                
                # 알림 전송
                if alerts:
                    message = format_alert_message(alerts)
                    send_telegram_message(message)
                    print(f"[ALERT] {len(alerts)}개 코인 알림")
                
                # 동적 주기 계산
                interval = self.get_optimal_interval(alerts, all_data)
                next_check = datetime.now() + timedelta(seconds=interval)
                
                print(f"[OK] 알림 없음 - 다음 체크: {next_check.strftime('%H:%M:%S')} ({interval//60}분)")
                print("="*60)
                
                # 대기
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n[INFO] 종료")
                break
            except Exception as e:
                print(f"\n[ERROR] {e}")
                time.sleep(60)  # 에러 시 1분 후 재시도

if __name__ == "__main__":
    monitor = SmartEnvelopeMonitor()
    monitor.run_smart_monitoring()
```

---

## 🔧 설정 가이드

### 최소 주기 설정
```python
# .env
MIN_CHECK_INTERVAL=60    # 최소 1분
MAX_CHECK_INTERVAL=1800  # 최대 30분
BASE_INTERVAL=600        # 기본 10분
```

### 우선순위 코인
```python
# config.json
{
  "priority_coins": ["BTC", "ETH", "BNB"],
  "priority_interval": 180,  # 우선 코인 3분
  "normal_interval": 600     # 일반 코인 10분
}
```

---

**마지막 업데이트**: 2025-01-XX  
**작성자**: OMG Trading System


