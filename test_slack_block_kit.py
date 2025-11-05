"""
Slack Block Kit 알림 테스트 스크립트
"""
import sys
import os

# 상위 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slack_notifier import send_slack_alert, send_slack_buy_execution_alert


def test_slack_alert():
    """매수 목표 접근 알림 테스트 (일반)"""
    print("=" * 60)
    print("테스트 1: 매수 목표 접근 알림 (일반)")
    print("=" * 60)
    
    if not send_slack_alert:
        print("\n[경고] Slack Webhook URL이 설정되지 않았습니다.")
        print("       .env 파일에 SLACK_WEBHOOK_URL을 설정해주세요.")
        return False
    
    alert_data = {
        'symbol': 'BTC',
        'name': 'Bitcoin',
        'rank': 1,
        'current_price': 45234.56,
        'target_price': 45000.00,
        'target': 'B1',
        'divergence': 0.52,
        'h_value': 80357.14,
        'is_first': False
    }
    
    print(f"\n알림 데이터:")
    print(f"  코인명: {alert_data['name']} ({alert_data['symbol']})")
    print(f"  시총 순위: {alert_data['rank']}")
    print(f"  현재가: ${alert_data['current_price']}")
    print(f"  매수목표: {alert_data['target']} - ${alert_data['target_price']}")
    print(f"  이격도: {alert_data['divergence']:.2f}%")
    print(f"  기준 고점: ${alert_data['h_value']}")
    print(f"  첫 자리: {alert_data['is_first']}")
    
    print(f"\nSlack 전송 중...")
    success = send_slack_alert(alert_data)
    
    if success:
        print("[성공] Slack 전송 성공!")
    else:
        print("[실패] Slack 전송 실패!")
    
    return success


def test_slack_alert_first():
    """매수 목표 접근 알림 테스트 (첫 자리)"""
    print("\n" + "=" * 60)
    print("테스트 2: 매수 목표 접근 알림 (첫 자리)")
    print("=" * 60)
    
    if not send_slack_alert:
        print("\n[경고] Slack Webhook URL이 설정되지 않았습니다.")
        return False
    
    alert_data = {
        'symbol': 'ETH',
        'name': 'Ethereum',
        'rank': 2,
        'current_price': 2856.34,
        'target_price': 2800.00,
        'target': 'B2',
        'divergence': 2.01,
        'h_value': 5384.62,
        'is_first': True
    }
    
    print(f"\n알림 데이터:")
    print(f"  코인명: {alert_data['name']} ({alert_data['symbol']})")
    print(f"  시총 순위: {alert_data['rank']}")
    print(f"  현재가: ${alert_data['current_price']}")
    print(f"  매수목표: {alert_data['target']} - ${alert_data['target_price']}")
    print(f"  이격도: {alert_data['divergence']:.2f}%")
    print(f"  기준 고점: ${alert_data['h_value']}")
    print(f"  첫 자리: {alert_data['is_first']}")
    
    print(f"\nSlack 전송 중...")
    success = send_slack_alert(alert_data)
    
    if success:
        print("[성공] Slack 전송 성공!")
    else:
        print("[실패] Slack 전송 실패!")
    
    return success


def test_slack_alert_small_value():
    """매수 목표 접근 알림 테스트 (작은 값 코인)"""
    print("\n" + "=" * 60)
    print("테스트 3: 매수 목표 접근 알림 (작은 값 코인)")
    print("=" * 60)
    
    if not send_slack_alert:
        print("\n[경고] Slack Webhook URL이 설정되지 않았습니다.")
        return False
    
    alert_data = {
        'symbol': 'SHIB',
        'name': 'Shiba Inu',
        'rank': 15,
        'current_price': 0.000012,
        'target_price': 0.000011,
        'target': 'B1',
        'divergence': 4.87,
        'h_value': 0.000019,
        'is_first': True
    }
    
    print(f"\n알림 데이터:")
    print(f"  코인명: {alert_data['name']} ({alert_data['symbol']})")
    print(f"  시총 순위: {alert_data['rank']}")
    print(f"  현재가: ${alert_data['current_price']}")
    print(f"  매수목표: {alert_data['target']} - ${alert_data['target_price']}")
    print(f"  이격도: {alert_data['divergence']:.2f}%")
    print(f"  기준 고점: ${alert_data['h_value']}")
    print(f"  첫 자리: {alert_data['is_first']}")
    
    print(f"\nSlack 전송 중...")
    success = send_slack_alert(alert_data)
    
    if success:
        print("[성공] Slack 전송 성공!")
    else:
        print("[실패] Slack 전송 실패!")
    
    return success


def test_slack_buy_execution_alert():
    """매수 실행 알림 테스트"""
    print("\n" + "=" * 60)
    print("테스트 4: 매수 실행 알림")
    print("=" * 60)
    
    if not send_slack_buy_execution_alert:
        print("\n[경고] Slack Webhook URL이 설정되지 않았습니다.")
        return False
    
    execution_data = {
        'symbol': 'PUMP',
        'name': 'Pump',
        'rank': 68,
        'target': 'B3',
        'target_price': 0.50,
        'candle_low': 0.48,
        'h_value': 1.0
    }
    
    price_data = {
        'avg_buy_price': 0.49,
        'sell_price': 0.61,
        'sell_threshold': 24.4
    }
    
    current_price = 0.50
    
    print(f"\n실행 데이터:")
    print(f"  코인명: {execution_data['name']} ({execution_data['symbol']})")
    print(f"  시총 순위: {execution_data['rank']}")
    print(f"  매수 목표: {execution_data['target']} - ${execution_data['target_price']}")
    print(f"  5분봉 저가: ${execution_data['candle_low']}")
    print(f"  현재가: ${current_price}")
    print(f"  평균매수가: ${price_data['avg_buy_price']}")
    print(f"  예상 매도가: ${price_data['sell_price']} (+{price_data['sell_threshold']:.1f}%)")
    
    print(f"\nSlack 전송 중...")
    success = send_slack_buy_execution_alert(execution_data, price_data, current_price)
    
    if success:
        print("[성공] Slack 전송 성공!")
    else:
        print("[실패] Slack 전송 실패!")
    
    return success


def main():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("Slack Block Kit 알림 테스트 시작")
    print("=" * 60)
    
    results = []
    
    # 테스트 1: 일반 알림
    results.append(("매수 목표 접근 알림 (일반)", test_slack_alert()))
    
    # 테스트 2: 첫 자리 알림
    results.append(("매수 목표 접근 알림 (첫 자리)", test_slack_alert_first()))
    
    # 테스트 3: 작은 값 코인
    results.append(("매수 목표 접근 알림 (작은 값)", test_slack_alert_small_value()))
    
    # 테스트 4: 매수 실행 알림
    results.append(("매수 실행 알림", test_slack_buy_execution_alert()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    for test_name, success in results:
        status = "[성공]" if success else "[실패]"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    print(f"\n총 {total}개 테스트 중 {passed}개 성공")
    
    if passed == total:
        print("\n[완료] 모든 테스트 성공!")
    else:
        print(f"\n[경고] {total - passed}개 테스트 실패")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n테스트가 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[오류] 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

