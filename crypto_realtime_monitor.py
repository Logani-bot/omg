#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
암호화폐 실시간 모니터링 시스템

기능:
1. 00:00에 DEBUG/ANALYSIS 파일 생성
2. 00:00에 ANALYSIS 파일에서 B1~B7 값 저장
3. 30분 간격으로 실시간 가격과 비교하여 알람 전송
4. 중복 알람 방지 (코인별, 매수목표별 하루 1회)
"""

import os
import sys
import pandas as pd
import requests
import time
import json
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import subprocess
import pathlib

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from telegram_notifier import send_telegram_message
except ImportError:
    print(f"Error: Could not import telegram_notifier from {current_dir}")
    print(f"Files in current directory: {os.listdir(current_dir)}")
    raise

class CryptoRealtimeMonitor:
    def __init__(self):
        # 현재 스크립트가 있는 디렉토리를 OMG 디렉토리로 설정
        self.omg_dir = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
        self.analysis_file = None
        self.monitoring_data = {}  # {symbol: {next_target, buy_levels, rank, name}}
        self.alert_history = {}  # {symbol: {target: sent_date}}
        self.alert_history_file = "alert_history.json"
        
        # 알람 이력 로드
        self.load_alert_history()
        
    def load_alert_history(self):
        """알람 이력 로드"""
        try:
            if os.path.exists(self.alert_history_file):
                with open(self.alert_history_file, 'r', encoding='utf-8') as f:
                    self.alert_history = json.load(f)
        except Exception as e:
            print(f"알람 이력 로드 실패: {e}")
            self.alert_history = {}
    
    def save_alert_history(self):
        """알람 이력 저장"""
        try:
            with open(self.alert_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.alert_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"알람 이력 저장 실패: {e}")
    
    def run_daily_update(self):
        """00:00에 실행되는 일일 업데이트"""
        print(f"[{datetime.now()}] 일일 업데이트 시작...")
        
        try:
            # OMG 디렉토리로 이동하여 DEBUG/ANALYSIS 파일 생성
            os.chdir(self.omg_dir)
            
            # DEBUG 파일 생성
            print("DEBUG 파일 생성 중...")
            result = subprocess.run([
                "python", "auto_debug_builder.py", "--limit-days", "1200"
            ], capture_output=True, text=True, encoding='cp949')
            
            if result.returncode != 0:
                print(f"DEBUG 파일 생성 실패: {result.stderr}")
                return False
            
            # ANALYSIS 파일 생성
            print("ANALYSIS 파일 생성 중...")
            result = subprocess.run([
                "python", "coin_analysis_excel.py"
            ], capture_output=True, text=True, encoding='cp949')
            
            if result.returncode != 0:
                print(f"ANALYSIS 파일 생성 실패: {result.stderr}")
                return False
            
            # 최신 ANALYSIS 파일 찾기
            output_dir = self.omg_dir / "output"
            analysis_files = list(output_dir.glob("coin_analysis_*.xlsx"))
            if not analysis_files:
                print("ANALYSIS 파일을 찾을 수 없습니다.")
                return False
            
            # 가장 최신 파일 선택
            self.analysis_file = max(analysis_files, key=os.path.getctime)
            print(f"ANALYSIS 파일 선택: {self.analysis_file.name}")
            
            # ANALYSIS 파일에서 모니터링 데이터 로드
            self.load_monitoring_data()
            
            # 알람 이력 초기화 (새로운 날)
            today = datetime.now().strftime("%Y-%m-%d")
            for symbol in list(self.alert_history.keys()):
                if isinstance(self.alert_history[symbol], dict):
                    for target in list(self.alert_history[symbol].keys()):
                        if self.alert_history[symbol][target] != today:
                            del self.alert_history[symbol][target]
                    # 빈 딕셔너리 제거
                    if not self.alert_history[symbol]:
                        del self.alert_history[symbol]
            
            print(f"[{datetime.now()}] 일일 업데이트 완료!")
            return True
            
        except Exception as e:
            print(f"일일 업데이트 실패: {e}")
            return False
        finally:
            # 원래 디렉토리로 복귀 (스크립트가 있는 디렉토리)
            os.chdir(self.omg_dir)
    
    def load_monitoring_data(self):
        """ANALYSIS 파일에서 모니터링 데이터 로드"""
        if not self.analysis_file or not self.analysis_file.exists():
            print("ANALYSIS 파일이 없습니다.")
            return
        
        try:
            df = pd.read_excel(self.analysis_file)
            self.monitoring_data = []
            
            for _, row in df.iterrows():
                symbol = row['심볼']
                next_target = row['다음매수목표']
                
                # 모니터링 제외 조건
                if pd.isna(next_target) or next_target in ['', 'STOP LOSS (실행됨)']:
                    continue
                
                # B1~B7 값 추출
                buy_levels = {}
                for i in range(1, 8):
                    level_key = f'B{i}'
                    if level_key in row and pd.notna(row[level_key]):
                        try:
                            # 콤마 제거 후 변환
                            value_str = str(row[level_key]).replace(',', '')
                            buy_levels[level_key] = float(value_str)
                        except (ValueError, TypeError):
                            continue
                
                # Stop_Loss 값 추출
                if 'Stop_Loss' in row and pd.notna(row['Stop_Loss']):
                    try:
                        value_str = str(row['Stop_Loss']).replace(',', '')
                        buy_levels['Stop_Loss'] = float(value_str)
                    except (ValueError, TypeError):
                        pass
                
                # 현재가 처리
                current_price = 0
                if pd.notna(row['현재가']):
                    try:
                        current_price_str = str(row['현재가']).replace(',', '')
                        current_price = float(current_price_str)
                    except (ValueError, TypeError):
                        current_price = 0
                
                # H값 처리
                h_value = 0
                if pd.notna(row['H값']):
                    try:
                        h_value_str = str(row['H값']).replace(',', '')
                        h_value = float(h_value_str)
                    except (ValueError, TypeError):
                        h_value = 0
                
                self.monitoring_data.append({
                    'symbol': symbol,
                    'next_target': next_target,
                    'buy_levels': buy_levels,
                    'rank': int(row['순위']) if pd.notna(row['순위']) else 0,
                    'name': row['코인명'],
                    'current_price': current_price,
                    'h_value': h_value
                })
            
            print(f"모니터링 데이터 로드 완료: {len(self.monitoring_data)}개 코인")
            
        except Exception as e:
            print(f"모니터링 데이터 로드 실패: {e}")
    
    def get_candle_low(self, symbol: str, interval: str = "5m") -> Optional[float]:
        """5분봉 저가 조회 (Binance Kline API) - 모니터링 간격에 맞춤"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": f"{symbol}USDT",
                "interval": interval,
                "limit": 1  # 최근 1개 봉
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                return float(data[0][3])  # 저가 (low)
            return None
            
        except Exception as e:
            print(f"{symbol} {interval}봉 저가 조회 실패: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회 (Binance Ticker API)"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {
                "symbol": f"{symbol}USDT"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data and "price" in data:
                return float(data["price"])
            return None
            
        except Exception as e:
            print(f"{symbol} 현재가 조회 실패: {e}")
            return None
    
    def calculate_divergence(self, current_price: float, target_price: float) -> float:
        """이격도 계산 (현재가 기준)"""
        if target_price == 0:
            return float('inf')
        return abs((current_price - target_price) / target_price) * 100
    
    def check_buy_execution(self, coin_data: Dict) -> Optional[Dict]:
        """5분봉 저가로 매수 실행 감지 (모니터링 간격에 맞춤)"""
        symbol = coin_data['symbol']
        next_target = coin_data['next_target']
        buy_levels = coin_data['buy_levels']
        
        # 다음 매수 목표가가 B1~B7인 경우만 체크
        if not next_target.startswith('B'):
            return None
        
        target_price = buy_levels.get(next_target)
        if not target_price:
            return None
        
        # 5분봉 저가 조회
        candle_low = self.get_candle_low(symbol, interval="5m")
        if not candle_low:
            return None
        
        # 저가가 목표가에 도달했는지 확인
        if candle_low <= target_price:
            return {
                'symbol': symbol,
                'target': next_target,
                'target_price': target_price,
                'candle_low': candle_low,
                'rank': coin_data['rank'],
                'name': coin_data['name'],
                'h_value': coin_data['h_value'],
                'buy_levels': buy_levels  # calculate_average_buy_and_sell_price에서 필요
            }
        
        return None
    
    def calculate_average_buy_and_sell_price(self, coin_data: Dict) -> Dict:
        """평균 매수선과 매도가 계산"""
        # execution_data에는 'target' 키가 있고, coin_data에는 'next_target' 키가 있음
        if 'next_target' in coin_data:
            target = coin_data['next_target']
        elif 'target' in coin_data:
            target = coin_data['target']
        else:
            raise KeyError("coin_data must have either 'next_target' or 'target' key")
        
        buy_levels = coin_data['buy_levels']
        
        # 매수 단계 추출 (B3 → 3)
        stage_num = int(target[1])
        
        # 1단계부터 현재 단계까지의 매수가들
        buy_prices = []
        for i in range(1, stage_num + 1):
            level_key = f'B{i}'
            if level_key in buy_levels and buy_levels[level_key]:
                buy_prices.append(buy_levels[level_key])
        
        # 평균 매수선 계산
        avg_buy_price = sum(buy_prices) / len(buy_prices)
        
        # 매도 기준 적용 (SELL_THRESHOLDS)
        sell_thresholds = {1: 7.7, 2: 17.3, 3: 24.4, 4: 37.4, 5: 52.7, 6: 79.9, 7: 98.5}
        sell_threshold = sell_thresholds[stage_num]
        sell_price = avg_buy_price * (1 + sell_threshold / 100)
        
        return {
            'avg_buy_price': avg_buy_price,
            'sell_price': sell_price,
            'sell_threshold': sell_threshold,
            'stage_num': stage_num
        }
    
    def get_allowed_targets(self, next_target: str) -> List[str]:
        """다음 매수 목표에 따른 허용 알람 목표 반환"""
        if next_target.startswith('B'):
            # B1~B7인 경우
            level_num = int(next_target[1])
            return [f'B{i}' for i in range(level_num, 8)] + ['STOP LOSS (실행 전)']
        elif next_target == 'STOP LOSS (실행 전)':
            return ['STOP LOSS (실행 전)']
        else:
            return []
    
    def check_alert_condition(self, coin_data: Dict, current_price: float) -> List[Dict]:
        """알람 조건 확인"""
        symbol = coin_data['symbol']
        next_target = coin_data['next_target']
        buy_levels = coin_data['buy_levels']
        
        # 허용되는 알람 목표들
        allowed_targets = self.get_allowed_targets(next_target)
        
        alerts = []
        
        for target in allowed_targets:
            if target not in buy_levels:
                continue
            
            target_price = buy_levels[target]
            divergence = self.calculate_divergence(current_price, target_price)
            
            # 5% 이내 접근 시 알람
            if divergence <= 5.0:
                # 중복 알람 확인
                today = datetime.now().strftime("%Y-%m-%d")
                if (symbol not in self.alert_history or 
                    not isinstance(self.alert_history[symbol], dict) or
                    target not in self.alert_history[symbol] or
                    self.alert_history[symbol][target] != today):
                    
                    alerts.append({
                        'symbol': symbol,
                        'target': target,
                        'target_price': target_price,
                        'current_price': current_price,
                        'divergence': divergence,
                        'rank': coin_data['rank'],
                        'name': coin_data['name'],
                        'h_value': coin_data['h_value']
                    })
        
        return alerts
    
    def send_alert(self, alert: Dict):
        """텔레그램 알람 전송"""
        try:
            # 알람 메시지 포맷팅 (새로운 형식)
            message = (
                f"🪙 <b>매수 목표 접근 알림</b>\n"
                f"────────────\n"
                f"코인명: {alert['name']} ({alert['symbol']})\n"
                f"시총 순위: {alert['rank']}\n\n"
                f"현재가: ${alert['current_price']:,.4f}\n"
                f"매수목표: <b>{alert['target']} - ${alert['target_price']:,.4f}</b>\n"
                f"이격도: <b>{alert['divergence']:.2f}%</b>\n"
                f"────────────\n"
                f"<tg-spoiler>* 기준 고점: ${alert['h_value']:,.2f}</tg-spoiler>"
            )
            
            # 텔레그램 전송 (모든 수신자에게)
            success = send_telegram_message(message, recipients=["all"])
            
            if success:
                # 알람 이력 업데이트
                today = datetime.now().strftime("%Y-%m-%d")
                if alert['symbol'] not in self.alert_history:
                    self.alert_history[alert['symbol']] = {}
                if not isinstance(self.alert_history[alert['symbol']], dict):
                    self.alert_history[alert['symbol']] = {}
                self.alert_history[alert['symbol']][alert['target']] = today
                self.save_alert_history()
                
                print(f"알람 전송 성공: {alert['symbol']} {alert['target']}")
            else:
                print(f"알람 전송 실패: {alert['symbol']} {alert['target']}")
                
        except Exception as e:
            print(f"알람 전송 오류: {e}")
    
    def send_buy_execution_alert(self, execution_data: Dict):
        """매수 실행 알림 전송"""
        try:
            # 평균 매수선과 매도가 계산
            price_data = self.calculate_average_buy_and_sell_price(execution_data)
            
            # 현재가 조회
            current_price = self.get_current_price(execution_data['symbol'])
            current_price_str = f"${current_price:,.4f}" if current_price else "조회실패"
            
            # 매수 실행 메시지 포맷팅 (새로운 형식)
            message = (
                f"⚡ <b>매수 실행 알림</b>\n"
                f"────────────\n"
                f"코인명: {execution_data['name']} ({execution_data['symbol']})\n"
                f"시총 순위: {execution_data['rank']}\n\n"
                f"매수 목표: {execution_data['target']} — ${execution_data['target_price']:,.2f}\n"
                f"5분봉 저가: ${execution_data['candle_low']:,.2f}\n\n"
                f"현재가: ${current_price:,.2f}\n"
                f"평균매수가: ${price_data['avg_buy_price']:,.2f}\n"
                f"예상 매도가: ${price_data['sell_price']:,.2f} (+{price_data['sell_threshold']:.1f}%)\n"
                f"────────────\n"
                f"<tg-spoiler>* 기준 고점: ${execution_data['h_value']:,.2f}</tg-spoiler>"
            )
            
            # 텔레그램 전송 (모든 수신자에게)
            success = send_telegram_message(message, recipients=["all"])
            
            if success:
                # 매수 실행 이력 업데이트
                today = datetime.now().strftime("%Y-%m-%d")
                symbol = execution_data['symbol']
                target = execution_data['target']
                
                if symbol not in self.alert_history:
                    self.alert_history[symbol] = {}
                if not isinstance(self.alert_history[symbol], dict):
                    self.alert_history[symbol] = {}
                
                # 매수 실행 이력 키 (접근 알림과 구분)
                execution_key = f"{target}_EXECUTED"
                self.alert_history[symbol][execution_key] = today
                self.save_alert_history()
                
                print(f"매수 실행 알림 전송 완료: {symbol} {target}")
            else:
                print(f"매수 실행 알림 전송 실패: {symbol} {target}")
                
        except Exception as e:
            print(f"매수 실행 알림 전송 실패: {e}")
    
    def run_monitoring_cycle(self):
        """5분 간격 모니터링 사이클"""
        if not self.monitoring_data:
            print("모니터링 데이터가 없습니다.")
            return
        
        print(f"[{datetime.now()}] 모니터링 사이클 시작...")
        print(f"체크할 코인 수: {len(self.monitoring_data)}개")
        
        alert_count = 0
        for coin_data in self.monitoring_data:
            try:
                symbol = coin_data['symbol']
                # 실시간 가격 조회
                current_price = self.get_current_price(symbol)
                if current_price is None:
                    continue
                
                # 알람 조건 확인 (접근 알림)
                alerts = self.check_alert_condition(coin_data, current_price)
                
                # 알람 전송
                if alerts:
                    alert_count += len(alerts)
                    print(f"  [{symbol}] 알람 발견: {len(alerts)}개")
                for alert in alerts:
                    print(f"    - {alert['target']}: 이격도 {alert['divergence']:.2f}%")
                    self.send_alert(alert)
                
                # 매수 실행 감지 (30분봉 저가 기준)
                execution_data = self.check_buy_execution(coin_data)
                if execution_data:
                    # 중복 실행 알림 방지
                    today = datetime.now().strftime("%Y-%m-%d")
                    symbol = execution_data['symbol']
                    target = execution_data['target']
                    execution_key = f"{target}_EXECUTED"
                    
                    if (symbol not in self.alert_history or 
                        not isinstance(self.alert_history[symbol], dict) or
                        execution_key not in self.alert_history[symbol] or
                        self.alert_history[symbol][execution_key] != today):
                        
                        self.send_buy_execution_alert(execution_data)
                
                # API 제한 방지
                time.sleep(0.1)
                
            except Exception as e:
                print(f"{symbol} 모니터링 오류: {e}")
        
        print(f"[{datetime.now()}] 모니터링 사이클 완료 - 알람 전송: {alert_count}개")
    
    def load_existing_analysis(self) -> bool:
        """기존 ANALYSIS 파일 로드 (DEBUG 파일 재생성 없이)"""
        try:
            output_dir = self.omg_dir / "output"
            analysis_files = list(output_dir.glob("coin_analysis_*.xlsx"))
            if not analysis_files:
                print("기존 ANALYSIS 파일이 없습니다. 일일 업데이트를 기다립니다.")
                return False
            
            # 가장 최신 파일 선택
            self.analysis_file = max(analysis_files, key=os.path.getctime)
            print(f"기존 ANALYSIS 파일 로드: {self.analysis_file.name}")
            
            # ANALYSIS 파일에서 모니터링 데이터 로드
            self.load_monitoring_data()
            return True
            
        except Exception as e:
            print(f"기존 ANALYSIS 파일 로드 실패: {e}")
            return False
    
    def start_monitoring(self):
        """모니터링 시작"""
        print("암호화폐 실시간 모니터링 시스템 시작...")
        
        # 스케줄 설정
        schedule.every().day.at("00:00").do(self.run_daily_update)
        schedule.every(5).minutes.do(self.run_monitoring_cycle)  # 5분 간격으로 변경
        
        # 기존 ANALYSIS 파일이 있으면 로드, 없으면 일일 업데이트를 기다림
        print("기존 데이터 확인 중...")
        if self.load_existing_analysis():
            print("기존 데이터 로드 완료 - 모니터링 시작")
        else:
            print("기존 데이터 없음 - 00:00 일일 업데이트를 기다립니다.")
            print("(수동으로 업데이트하려면 run_daily_analysis.bat 실행)")
        
        # 메인 루프
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 스케줄 확인
        except KeyboardInterrupt:
            print("모니터링 중단")
        except Exception as e:
            print(f"모니터링 오류: {e}")

def main():
    monitor = CryptoRealtimeMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()
