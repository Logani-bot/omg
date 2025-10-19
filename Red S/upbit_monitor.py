#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
업비트 코인 모니터링 시스템
- 1시간 단위로 업비트 코인 등락률 확인
- -15% 이하 종목이 15개 이상일 때 텔레그램 알람
- 하루 최대 1회 시작/끝 알람 제한
"""

import requests
import json
import time
import schedule
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
import os
from telegram_notifier import TelegramNotifier

class UpbitMonitor:
    def __init__(self, config_file: str = "config.json"):
        """업비트 모니터 초기화"""
        self.config = self.load_config(config_file)
        self.telegram = TelegramNotifier(self.config.get('telegram_bot_token'))
        self.chat_id = self.config.get('telegram_chat_id')
        
        # 알람 상태 관리 (날짜별로 기록)
        self.alert_status_file = "alert_status.json"
        self.alert_status = self.load_alert_status()
        
        # 로깅 설정
        self.setup_logging()
        
        # API 엔드포인트
        self.upbit_base_url = "https://api.upbit.com/v1"
        
    def load_config(self, config_file: str) -> Dict:
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"설정 파일 {config_file}을 찾을 수 없습니다.")
            return {}
        except json.JSONDecodeError:
            self.logger.error(f"설정 파일 {config_file}의 JSON 형식이 잘못되었습니다.")
            return {}
    
    def load_alert_status(self) -> Dict:
        """알람 상태 파일 로드"""
        try:
            with open(self.alert_status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    def save_alert_status(self):
        """알람 상태 파일 저장"""
        try:
            with open(self.alert_status_file, 'w', encoding='utf-8') as f:
                json.dump(self.alert_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"알람 상태 저장 실패: {e}")
    
    def setup_logging(self):
        """로깅 설정"""
        log_filename = f"upbit_monitor_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_all_markets(self) -> List[Dict]:
        """모든 마켓 정보 조회"""
        try:
            url = f"{self.upbit_base_url}/market/all"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"마켓 정보 조회 실패: {e}")
            return []
    
    def get_ticker_info(self, markets: List[str]) -> List[Dict]:
        """티커 정보 조회 (현재가, 등락률 등)"""
        try:
            url = f"{self.upbit_base_url}/ticker"
            params = {'markets': ','.join(markets)}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"티커 정보 조회 실패: {e}")
            return []
    
    def filter_krw_markets(self, markets: List[Dict]) -> List[str]:
        """KRW 마켓만 필터링"""
        krw_markets = []
        for market in markets:
            if market.get('market', '').startswith('KRW-'):
                krw_markets.append(market['market'])
        return krw_markets
    
    def find_declining_coins(self, threshold: float = -15.0) -> List[Dict]:
        """등락률이 임계값 이하인 코인 찾기"""
        # 모든 마켓 조회
        all_markets = self.get_all_markets()
        if not all_markets:
            return []
        
        # KRW 마켓만 필터링
        krw_markets = self.filter_krw_markets(all_markets)
        if not krw_markets:
            return []
        
        # 티커 정보 조회
        ticker_data = self.get_ticker_info(krw_markets)
        if not ticker_data:
            return []
        
        # 등락률이 임계값 이하인 코인 필터링
        declining_coins = []
        for ticker in ticker_data:
            change_rate = ticker.get('signed_change_rate', 0) * 100  # 퍼센트로 변환
            if change_rate <= threshold:
                declining_coins.append({
                    'market': ticker.get('market', ''),
                    'korean_name': ticker.get('korean_name', ''),
                    'english_name': ticker.get('english_name', ''),
                    'trade_price': ticker.get('trade_price', 0),
                    'change_rate': change_rate,
                    'change_price': ticker.get('signed_change_price', 0)
                })
        
        # 등락률 순으로 정렬 (가장 많이 하락한 순)
        declining_coins.sort(key=lambda x: x['change_rate'])
        
        return declining_coins
    
    def check_alert_condition(self) -> Dict:
        """알람 조건 확인"""
        declining_coins = self.find_declining_coins()
        count = len(declining_coins)
        
        today = date.today().isoformat()
        
        # 오늘 이미 알람을 보냈는지 확인
        today_status = self.alert_status.get(today, {})
        start_sent = today_status.get('start_sent', False)
        end_sent = today_status.get('end_sent', False)
        
        result = {
            'count': count,
            'declining_coins': declining_coins,
            'should_send_start': False,
            'should_send_end': False,
            'start_sent': start_sent,
            'end_sent': end_sent
        }
        
        # 시작 알람 조건: 15개 이상이고 아직 시작 알람을 보내지 않았을 때
        if count >= 15 and not start_sent:
            result['should_send_start'] = True
            self.alert_status[today] = self.alert_status.get(today, {})
            self.alert_status[today]['start_sent'] = True
            self.alert_status[today]['start_time'] = datetime.now().isoformat()
            self.save_alert_status()
        
        # 끝 알람 조건: 15개 미만이고 시작 알람은 보냈지만 끝 알람은 보내지 않았을 때
        elif count < 15 and start_sent and not end_sent:
            result['should_send_end'] = True
            self.alert_status[today] = self.alert_status.get(today, {})
            self.alert_status[today]['end_sent'] = True
            self.alert_status[today]['end_time'] = datetime.now().isoformat()
            self.save_alert_status()
        
        return result
    
    def send_start_alert(self, alert_data: Dict):
        """시작 알람 전송"""
        count = alert_data['count']
        declining_coins = alert_data['declining_coins']
        
        # 상위 10개 코인만 표시
        top_coins = declining_coins[:10]
        
        message = f"🚨 업비트 급락 알림 🚨\n\n"
        message += f"📊 현재 -15% 이하 하락 종목: {count}개\n"
        message += f"⏰ 알림 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"📉 상위 하락 종목 (상위 10개):\n"
        
        for i, coin in enumerate(top_coins, 1):
            message += f"{i:2d}. {coin['korean_name']} ({coin['market']})\n"
            message += f"    💰 가격: {coin['trade_price']:,.0f}원\n"
            message += f"    📉 등락률: {coin['change_rate']:.2f}%\n"
            message += f"    💸 등락가: {coin['change_price']:+,.0f}원\n\n"
        
        if count > 10:
            message += f"... 외 {count - 10}개 종목 추가\n\n"
        
        message += "⚠️ 투자 시 신중한 판단을 바랍니다."
        
        try:
            self.telegram.send_message(self.chat_id, message)
            self.logger.info(f"시작 알람 전송 완료: {count}개 종목")
        except Exception as e:
            self.logger.error(f"시작 알람 전송 실패: {e}")
    
    def send_end_alert(self, alert_data: Dict):
        """끝 알람 전송"""
        count = alert_data['count']
        
        message = f"✅ 업비트 급락 알림 종료 ✅\n\n"
        message += f"📊 현재 -15% 이하 하락 종목: {count}개\n"
        message += f"⏰ 알림 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"ℹ️ 안내사항:\n"
        message += f"• 당일 추가로 -15% 이하의 종목이 15개 발생하더라도\n"
        message += f"• 해당 날에는 추가 검색을 하지 않습니다\n"
        message += f"• 투자에 참고하시기 바랍니다\n\n"
        message += f"📈 다음 알림은 내일부터 가능합니다."
        
        try:
            self.telegram.send_message(self.chat_id, message)
            self.logger.info(f"끝 알람 전송 완료: {count}개 종목")
        except Exception as e:
            self.logger.error(f"끝 알람 전송 실패: {e}")
    
    def run_monitoring(self):
        """모니터링 실행"""
        try:
            self.logger.info("업비트 모니터링 시작")
            
            alert_data = self.check_alert_condition()
            
            self.logger.info(f"현재 -15% 이하 하락 종목: {alert_data['count']}개")
            
            if alert_data['should_send_start']:
                self.send_start_alert(alert_data)
            elif alert_data['should_send_end']:
                self.send_end_alert(alert_data)
            else:
                self.logger.info("알람 조건 미충족 또는 이미 알람 전송 완료")
                
        except Exception as e:
            self.logger.error(f"모니터링 실행 중 오류: {e}")
    
    def start_scheduler(self):
        """스케줄러 시작"""
        # 매시간 정각에 실행
        schedule.every().hour.at(":00").do(self.run_monitoring)
        
        self.logger.info("업비트 모니터링 스케줄러 시작 (1시간 간격)")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 스케줄 확인

def main():
    """메인 함수"""
    monitor = UpbitMonitor()
    
    # 즉시 한 번 실행 (테스트용)
    monitor.run_monitoring()
    
    # 스케줄러 시작
    monitor.start_scheduler()

if __name__ == "__main__":
    main()


