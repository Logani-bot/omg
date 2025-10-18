"""
Envelope Alert Monitor - 반복 실행 버전
지정된 간격으로 자동 모니터링 및 텔레그램 알림
"""

from __future__ import annotations
import time
import os
from datetime import datetime
from dotenv import load_dotenv

from envelope_alert import AlertMonitor, format_alert_message, send_telegram_message

# 환경 변수 로드
load_dotenv()

# ========== 설정 ==========
MONITOR_INTERVAL_MINUTES = int(os.getenv('MONITOR_INTERVAL_MINUTES', '10'))  # 기본 10분
SAVE_EXCEL_EVERY_N_RUNS = int(os.getenv('SAVE_EXCEL_EVERY_N_RUNS', '6'))  # 6회마다 엑셀 저장 (1시간마다)


def run_single_check(save_excel: bool = False):
    """
    단일 체크 실행
    
    Args:
        save_excel: 엑셀 파일 저장 여부
    """
    print(f"\n{'='*60}")
    print(f"모니터링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    monitor = AlertMonitor()
    
    # 전체 코인 모니터링
    alerts, all_coins_data = monitor.monitor_all_coins()
    
    # 엑셀 저장 (주기적으로만)
    if save_excel:
        monitor.save_results(alerts, all_coins_data)
        print("[OK] 엑셀 파일 저장 완료")
    
    # 텔레그램 알림 전송 (알림 대상이 있을 경우)
    if alerts:
        print(f"\n{'='*60}")
        print(f"[ALERT] {len(alerts)}개 코인이 하단선 5% 이내 접근!")
        print(f"{'='*60}")
        
        for alert in alerts:
            print(f"  - {alert['코인명']} ({alert['심볼']}): "
                  f"현재가 ${alert['현재가']:.4f}, "
                  f"하단선 ${alert['Envelope하단']:.4f}, "
                  f"이격도 {alert['이격도(%)']:.2f}%")
        
        message = format_alert_message(alerts)
        send_telegram_message(message)
    else:
        print("\n[OK] 알림 대상 코인 없음")
    
    print(f"\n{'='*60}")
    print(f"모니터링 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"다음 체크: {MONITOR_INTERVAL_MINUTES}분 후")
    print(f"{'='*60}\n")


def main():
    """메인 루프"""
    print("="*60)
    print("Envelope Alert Monitor - 자동 반복 모니터링")
    print("="*60)
    print(f"체크 간격: {MONITOR_INTERVAL_MINUTES}분")
    print(f"엑셀 저장: {SAVE_EXCEL_EVERY_N_RUNS}회마다 ({MONITOR_INTERVAL_MINUTES * SAVE_EXCEL_EVERY_N_RUNS}분마다)")
    print("종료: Ctrl+C")
    print("="*60)
    
    run_count = 0
    
    try:
        while True:
            run_count += 1
            save_excel = (run_count % SAVE_EXCEL_EVERY_N_RUNS == 0)
            
            run_single_check(save_excel=save_excel)
            
            # 대기
            time.sleep(MONITOR_INTERVAL_MINUTES * 60)
            
    except KeyboardInterrupt:
        print("\n\n[INFO] 모니터링 종료 (사용자 중단)")
    except Exception as e:
        print(f"\n\n[ERROR] 예상치 못한 오류: {str(e)}")
        raise


if __name__ == "__main__":
    main()

