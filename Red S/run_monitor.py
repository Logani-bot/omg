#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
업비트 모니터링 실행 스크립트
"""

import sys
import os
from upbit_monitor import UpbitMonitor

def main():
    """메인 실행 함수"""
    print("🚀 업비트 모니터링 시스템 시작")
    print("=" * 50)
    
    try:
        # 모니터 인스턴스 생성
        monitor = UpbitMonitor()
        
        # 설정 확인
        if not monitor.config.get('telegram_bot_token') or monitor.config.get('telegram_bot_token') == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            print("❌ 오류: 텔레그램 봇 토큰이 설정되지 않았습니다.")
            print("config.json 파일에서 telegram_bot_token을 설정해주세요.")
            return
        
        if not monitor.config.get('telegram_chat_id') or monitor.config.get('telegram_chat_id') == "YOUR_TELEGRAM_CHAT_ID_HERE":
            print("❌ 오류: 텔레그램 채팅 ID가 설정되지 않았습니다.")
            print("config.json 파일에서 telegram_chat_id를 설정해주세요.")
            return
        
        print("✅ 설정 확인 완료")
        print("📊 모니터링 시작 (1시간 간격)")
        print("⏹️  종료하려면 Ctrl+C를 누르세요")
        print("=" * 50)
        
        # 스케줄러 시작
        monitor.start_scheduler()
        
    except KeyboardInterrupt:
        print("\n⏹️  모니터링이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

