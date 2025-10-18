"""
Envelope Alert System
45일 이동평균 기준 Envelope 하한선 근접 알림 시스템
"""

from __future__ import annotations
import pathlib
import os
from typing import List, Dict, Optional, Any
from datetime import datetime

import pandas as pd
import requests
from dotenv import load_dotenv

from config.adapters import BinanceClient
from universe_selector import get_top30_coins

# 환경 변수 로드
load_dotenv()

# ========== 설정 ==========
ENVELOPE_DAYS = 45  # Envelope 이동평균 기간
ALPHA = 0.45  # Envelope 상하단 폭 (45%)
PROXIMITY_THRESHOLD = 0.05  # 근접 기준 (5%)

# 텔레그램 설정
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

OUTPUT_DIR = pathlib.Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ========== 텔레그램 알림 ==========
def send_telegram_message(message: str) -> bool:
    """
    텔레그램 메시지 전송
    
    Args:
        message: 전송할 메시지
    
    Returns:
        성공 여부
    """
    if not TELEGRAM_ENABLED:
        print("[INFO] 텔레그램 설정이 없습니다. .env 파일을 확인하세요.")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("[OK] 텔레그램 메시지 전송 성공")
        return True
    except Exception as e:
        print(f"[ERROR] 텔레그램 메시지 전송 실패: {str(e)}")
        return False


def format_alert_message(alerts: List[Dict[str, Any]]) -> str:
    """
    알림 메시지 포맷팅
    
    Args:
        alerts: 알림 대상 코인 리스트
    
    Returns:
        포맷된 메시지
    """
    if not alerts:
        return "알림 대상 코인이 없습니다."
    
    msg = "🚨 <b>Red S 근접 알림</b> 🚨\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, alert in enumerate(alerts, 1):
        msg += f"<b>{i}. {alert['코인명']} ({alert['심볼']})</b>\n"
        msg += f"   - 현재가: ${alert['현재가']:,.4f}\n"
        msg += f"   - 하단선: ${alert['Envelope하단']:,.4f}\n"
        msg += f"   - 이격도: {alert['이격도(%)']:.2f}%\n"
        
        if i < len(alerts):
            msg += "\n"
    
    return msg


class EnvelopeCalculator:
    """Envelope 계산 클래스"""
    
    def __init__(self, period: int = ENVELOPE_DAYS, alpha: float = ALPHA):
        self.period = period
        self.alpha = alpha
    
    def calculate_envelope(self, prices: pd.Series) -> Dict[str, float]:
        """
        45일 이동평균 기준 Envelope 계산
        
        Args:
            prices: 종가 시리즈 (최근 N일)
        
        Returns:
            {
                'sma': 45일 이동평균,
                'upper': 상단선 (SMA × 1.45),
                'lower': 하단선 (SMA × 0.55)
            }
        """
        if len(prices) < self.period:
            return {'sma': None, 'upper': None, 'lower': None}
        
        # 최근 N일 이동평균
        sma = prices.tail(self.period).mean()
        
        # Envelope 상하단선
        upper = sma * (1 + self.alpha)
        lower = sma * (1 - self.alpha)
        
        return {
            'sma': float(sma),
            'upper': float(upper),
            'lower': float(lower)
        }


class AlertMonitor:
    """알림 모니터링 클래스"""
    
    def __init__(self):
        self.client = BinanceClient()
        self.calculator = EnvelopeCalculator()
        self.alerts: List[Dict[str, Any]] = []
    
    def check_coin(self, symbol: str, coin_name: str, collect_all: bool = False) -> Optional[Dict[str, Any]]:
        """
        개별 코인 체크
        
        Args:
            symbol: 심볼 (BTCUSDT)
            coin_name: 코인 이름 (Bitcoin)
            collect_all: True면 알림 대상이 아니어도 데이터 반환
        
        Returns:
            알림 대상이면 정보 딕셔너리, 아니면 None (collect_all=True면 항상 반환)
        """
        try:
            # OHLCV 데이터 가져오기 (최근 50일치)
            df = self.client.get_ohlc_daily(symbol, limit=50)
            
            if df.empty or len(df) < ENVELOPE_DAYS:
                print(f"  {symbol}: 데이터 부족")
                return None
            
            # Envelope 계산
            envelope = self.calculator.calculate_envelope(df['close'])
            
            if envelope['lower'] is None:
                return None
            
            # 현재가 (최근 종가)
            current_price = float(df['close'].iloc[-1])
            
            # 하단선과의 거리 계산
            lower_band = envelope['lower']
            distance_pct = ((current_price - lower_band) / lower_band) * 100
            
            # 기본 정보
            coin_info = {
                '코인명': coin_name,
                '심볼': symbol.replace('USDT', ''),
                '현재가': current_price,
                'SMA45': envelope['sma'],
                'Envelope하단': envelope['lower'],
                '이격도(%)': distance_pct
            }
            
            # collect_all=True면 모든 데이터 반환
            if collect_all:
                return coin_info
            
            # 알림 조건: 현재가가 하단선 5% 이내
            if current_price <= lower_band * (1 + PROXIMITY_THRESHOLD):
                alert_info = {
                    **coin_info,
                    'Envelope상단': envelope['upper'],
                    '체크시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                print(f"  [ALERT] {symbol}: 현재가 {current_price:.4f}, 하단선 {lower_band:.4f}, 거리 {distance_pct:.2f}%")
                return alert_info
            else:
                print(f"  [OK] {symbol}: 정상 (거리 {distance_pct:.2f}%)")
                return None
                
        except Exception as e:
            print(f"  [SKIP] {symbol}: 에러 - {str(e)}")
            return None
    
    def monitor_all_coins(self) -> tuple:
        """
        전체 코인 모니터링
        
        Returns:
            (알림 대상 코인 리스트, 전체 코인 데이터 리스트)
        """
        print(f"\n{'='*60}")
        print(f"Envelope Alert System - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"설정: {ENVELOPE_DAYS}일 이동평균, α={ALPHA*100}%, 근접기준={PROXIMITY_THRESHOLD*100}%")
        print(f"{'='*60}\n")
        
        # Top 50 코인 리스트 가져오기
        coins = get_top30_coins()
        print(f"모니터링 대상: {len(coins)}개 코인\n")
        
        alerts = []
        all_coins_data = []
        
        for coin in coins:
            symbol = coin['Symbol']
            name = coin['Name']
            
            # 알림 체크
            alert = self.check_coin(symbol, name, collect_all=False)
            if alert:
                alerts.append(alert)
            
            # 전체 데이터 수집 (검증용)
            coin_data = self.check_coin(symbol, name, collect_all=True)
            if coin_data:
                all_coins_data.append(coin_data)
        
        self.alerts = alerts
        return alerts, all_coins_data
    
    def save_results(self, alerts: List[Dict[str, Any]], all_coins_data: List[Dict[str, Any]] = None):
        """
        결과를 CSV/Excel로 저장
        
        Args:
            alerts: 알림 대상 코인 리스트
            all_coins_data: 전체 코인 데이터 (검증용)
        """
        # 전체 코인 데이터 저장 (검증용)
        if all_coins_data:
            df_all = pd.DataFrame(all_coins_data)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_all_path = OUTPUT_DIR / f"envelope_all_coins_{timestamp}.xlsx"
            
            with pd.ExcelWriter(excel_all_path, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name='전체코인', index=False)
                
                worksheet = writer.sheets['전체코인']
                
                # 컬럼 너비 조정
                column_widths = {
                    'A': 15,  # 코인명
                    'B': 10,  # 심볼
                    'C': 12,  # 현재가
                    'D': 15,  # SMA45
                    'E': 18,  # Envelope하단
                    'F': 12   # 이격도(%)
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
                
                # 숫자 포맷 적용
                from openpyxl.styles import numbers
                
                for row_idx in range(2, len(df_all) + 2):  # 헤더 제외
                    # 현재가 기준으로 소수점 자리 결정
                    current_price_cell = worksheet[f'C{row_idx}']
                    current_price = current_price_cell.value
                    
                    if current_price is not None:
                        # 소수점 자리 결정
                        if current_price <= 1:
                            price_format = '#,##0.000000'  # 소수점 6자리
                        elif current_price <= 10:
                            price_format = '#,##0.0000'    # 소수점 4자리
                        else:
                            price_format = '#,##0.00'      # 소수점 2자리
                        
                        # 현재가, SMA45, Envelope하단에 동일한 포맷 적용
                        for col in ['C', 'D', 'E']:
                            cell = worksheet[f'{col}{row_idx}']
                            if cell.value is not None:
                                cell.number_format = price_format
                    
                    # 이격도(%): 퍼센트 표시 (그대로 유지)
                    cell_f = worksheet[f'F{row_idx}']
                    if cell_f.value is not None:
                        cell_f.number_format = '0.00"%"'
            
            print(f"\n[OK] 전체 코인 엑셀 저장: {excel_all_path}")
        
        if not alerts:
            print("\n알림 대상 코인이 없습니다.")
            return
        
        # DataFrame 생성
        df = pd.DataFrame(alerts)
        
        # 파일명 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = OUTPUT_DIR / f"envelope_alerts_{timestamp}.csv"
        excel_path = OUTPUT_DIR / f"envelope_alerts_{timestamp}.xlsx"
        
        # CSV 저장
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\n[OK] CSV 저장: {csv_path}")
        
        # Excel 저장 (포맷팅 포함)
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='알림', index=False)
            
            worksheet = writer.sheets['알림']
            
            # 컬럼 너비 조정
            column_widths = {
                'A': 15,  # 코인명
                'B': 10,  # 심볼
                'C': 12,  # 현재가
                'D': 12,  # SMA45
                'E': 15,  # Envelope상단
                'F': 15,  # Envelope하단
                'G': 15,  # 이격도(%)
                'H': 20   # 체크시간
            }
            
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
            
            # 숫자 포맷 적용
            for row_idx in range(2, len(df) + 2):  # 헤더 제외
                # 현재가 기준으로 소수점 자리 결정
                current_price_cell = worksheet[f'C{row_idx}']
                current_price = current_price_cell.value
                
                if current_price is not None:
                    # 소수점 자리 결정
                    if current_price <= 1:
                        price_format = '#,##0.000000'  # 소수점 6자리
                    elif current_price <= 10:
                        price_format = '#,##0.0000'    # 소수점 4자리
                    else:
                        price_format = '#,##0.00'      # 소수점 2자리
                    
                    # 현재가, SMA45, Envelope상단, Envelope하단에 동일한 포맷 적용
                    for col in ['C', 'D', 'E', 'F']:
                        cell = worksheet[f'{col}{row_idx}']
                        if cell.value is not None:
                            cell.number_format = price_format
                
                # 이격도(%): 퍼센트 표시 (그대로 유지)
                cell_g = worksheet[f'G{row_idx}']
                if cell_g.value is not None:
                    cell_g.number_format = '0.00"%"'
        
        print(f"[OK] Excel 저장: {excel_path}")
        
        # 요약 출력
        print(f"\n{'='*60}")
        print(f"알림 요약: {len(alerts)}개 코인이 하단선 5% 이내 접근")
        print(f"{'='*60}")
        for alert in alerts:
            print(f"  - {alert['코인명']} ({alert['심볼']}): "
                  f"현재가 ${alert['현재가']:.4f}, "
                  f"하단선 ${alert['Envelope하단']:.4f}, "
                  f"이격도 {alert['이격도(%)']:.2f}%")
        print(f"{'='*60}\n")


def main():
    """메인 함수"""
    monitor = AlertMonitor()
    
    # 전체 코인 모니터링
    alerts, all_coins_data = monitor.monitor_all_coins()
    
    # 결과 저장 (알림 대상 + 전체 코인 데이터)
    monitor.save_results(alerts, all_coins_data)
    
    # 텔레그램 알림 전송 (알림 대상이 있을 경우)
    if alerts:
        print(f"\n{'='*60}")
        print("텔레그램 알림 전송 중...")
        print(f"{'='*60}")
        
        message = format_alert_message(alerts)
        send_telegram_message(message)
    else:
        print("\n[INFO] 알림 대상 코인이 없어 텔레그램 메시지를 보내지 않습니다.")
    
    print("\n모니터링 완료!")


if __name__ == "__main__":
    main()

