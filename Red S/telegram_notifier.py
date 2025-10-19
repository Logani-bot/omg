#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
텔레그램 알림 시스템
"""

import requests
import logging
from typing import Optional

class TelegramNotifier:
    def __init__(self, bot_token: str):
        """텔레그램 알림 초기화"""
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)
    
    def send_message(self, chat_id: str, message: str) -> bool:
        """텔레그램 메시지 전송"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            self.logger.info("텔레그램 메시지 전송 성공")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"텔레그램 메시지 전송 실패: {e}")
            return False
        except Exception as e:
            self.logger.error(f"텔레그램 메시지 전송 중 오류: {e}")
            return False
    
    def test_connection(self, chat_id: str) -> bool:
        """텔레그램 연결 테스트"""
        test_message = "🤖 업비트 모니터링 봇 연결 테스트\n\n✅ 정상적으로 연결되었습니다!"
        return self.send_message(chat_id, test_message)

