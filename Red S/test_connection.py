#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
텔레그램 연결 테스트 스크립트
"""

import json
from telegram_notifier import TelegramNotifier

def test_telegram_connection():
    """텔레그램 연결 테스트"""
    try:
        # 설정 파일 로드
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        bot_token = config.get('telegram_bot_token')
        chat_id = config.get('telegram_chat_id')
        
        if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            print("❌ 텔레그램 봇 토큰이 설정되지 않았습니다.")
            print("config.json 파일에서 telegram_bot_token을 설정해주세요.")
            return False
        
        if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID_HERE":
            print("❌ 텔레그램 채팅 ID가 설정되지 않았습니다.")
            print("config.json 파일에서 telegram_chat_id를 설정해주세요.")
            return False
        
        # 텔레그램 연결 테스트
        notifier = TelegramNotifier(bot_token)
        success = notifier.test_connection(chat_id)
        
        if success:
            print("✅ 텔레그램 연결 테스트 성공!")
            return True
        else:
            print("❌ 텔레그램 연결 테스트 실패!")
            return False
            
    except FileNotFoundError:
        print("❌ config.json 파일을 찾을 수 없습니다.")
        return False
    except json.JSONDecodeError:
        print("❌ config.json 파일의 JSON 형식이 잘못되었습니다.")
        return False
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    test_telegram_connection()

