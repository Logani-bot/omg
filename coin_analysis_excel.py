#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Top 50 코인 분석 엑셀 생성기

기능:
1. Top 50 코인 정보 수집 (시총순위, 코인 이름, 시총, 현재가)
2. 디버그 파일에서 최근 H값 추출
3. 매수선 계산 (44%, 48%, 54%, 59%, 65%, 72%, 79%)
4. 현재가 대비 매수선 거리 계산
5. 종합 엑셀 파일 생성
"""

import os
import pandas as pd
import pathlib
from typing import Dict, List, Optional, Tuple
import requests
import time
from datetime import datetime

# 제외할 심볼들 (래핑된 토큰)
EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}

class CoinAnalysisExcel:
    def __init__(self):
        self.output_dir = pathlib.Path("output")
        self.state_dir = pathlib.Path("debug")  # debug 폴더의 디버그 파일 사용
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_top100_coins_with_prices(self) -> List[Dict]:
        """CoinGecko에서 Top 100 코인 정보와 현재가를 가져옴"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "price_change_percentage": "24h",
            "locale": "en",
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            coins = []
            rank = 1
            for coin in data:
                symbol = coin.get("symbol", "").upper()
                name = coin.get("name", "")
                
                # 제외 조건 적용
                if symbol in EXCLUDE_SYMBOLS:
                    continue
                if any(keyword in name.upper() for keyword in EXCLUDE_NAME_KEYWORDS):
                    continue
                
                coins.append({
                    "순위": rank,
                    "코인명": name,
                    "심볼": symbol,
                    "시가총액": coin.get("market_cap", 0),
                    "현재가": coin.get("current_price", 0),
                    "24h변동률": coin.get("price_change_percentage_24h", 0)  # 백분율 형태로 저장
                })
                rank += 1
                
                # Top 100개까지만
                if len(coins) >= 100:
                    break
            
            return coins
            
        except Exception as e:
            print(f"코인 정보 수집 실패: {e}")
            return []
    
    def get_latest_buy_progress(self, symbol: str) -> Dict:
        """EVENT 기반으로 다음 매수 목표를 결정하는 새로운 로직"""
        debug_file = self.state_dir / f"{symbol}_debug.csv"
        
        if not debug_file.exists():
            return {"status": "no_debug_file", "next_buy_target": None, "current_price": None, "h_value": None}
            
        try:
            df = pd.read_csv(debug_file)
            if df.empty:
                return {"status": "empty_debug", "next_buy_target": None, "current_price": None, "h_value": None}
            
            # 가장 최근 데이터
            latest_row = df.iloc[-1]
            current_price = latest_row['close']
            h_value = latest_row['H'] if pd.notna(latest_row['H']) else None
            
            if not h_value:
                return {"status": "no_h_value", "next_buy_target": None, "current_price": current_price, "h_value": None}
            
            # DEBUG 파일에서 B1~B7 값과 Stop_Loss 값 직접 가져오기
            buy_levels = {
                'B1': latest_row['B1'] if pd.notna(latest_row['B1']) else None,
                'B2': latest_row['B2'] if pd.notna(latest_row['B2']) else None,
                'B3': latest_row['B3'] if pd.notna(latest_row['B3']) else None,
                'B4': latest_row['B4'] if pd.notna(latest_row['B4']) else None,
                'B5': latest_row['B5'] if pd.notna(latest_row['B5']) else None,
                'B6': latest_row['B6'] if pd.notna(latest_row['B6']) else None,
                'B7': latest_row['B7'] if pd.notna(latest_row['B7']) else None,
                'Stop_Loss': latest_row['Stop_Loss'] if pd.notna(latest_row['Stop_Loss']) else None,
            }
            
            # EVENT가 있는 행들만 필터링
            events_df = df[df['event'].notna() & (df['event'] != '')]
            
            if events_df.empty:
                # EVENT가 없으면 B1이 다음 목표
                next_buy_target = "B1"
                next_buy_price = buy_levels['B1']
                status = "no_events_b1_target"
            else:
                # 가장 최근 EVENT 분석
                latest_event_row = events_df.iloc[-1]
                latest_event = latest_event_row['event']
                
                if latest_event.startswith('BUY') or latest_event.startswith('ADD'):
                    # BUY/ADD 이벤트: 한 차수 아래가 다음 목표
                    stage = latest_event_row['stage']
                    if pd.notna(stage) and str(stage).replace('.0', '').isdigit():
                        stage_num = int(stage)
                        if stage_num < 7:
                            next_buy_target = f"B{stage_num + 1}"
                            next_buy_price = buy_levels[next_buy_target]
                            status = f"buy_add_next_target_{next_buy_target}"
                        else:
                            # B7까지 완료된 경우 - STOP LOSS 대기 상태 (실행 전)
                            next_buy_target = "STOP LOSS (실행 전)"
                            next_buy_price = buy_levels['Stop_Loss'] if buy_levels['Stop_Loss'] is not None else h_value * 0.19
                            status = "buy_add_max"
                    else:
                        # stage 정보가 없으면 B2가 목표
                        next_buy_target = "B2"
                        next_buy_price = buy_levels['B2']
                        status = "buy_add_no_stage_b2"
                
                elif latest_event.startswith('SELL'):
                    # SELL 이벤트: forbidden_levels_above_last_sell 값에 따라 다음 목표 결정
                    forbidden_levels = latest_event_row['forbidden_levels_above_last_sell']
                    if pd.notna(forbidden_levels) and str(forbidden_levels).isdigit():
                        forbidden_num = int(forbidden_levels)
                        if forbidden_num == 0:
                            # 모든 레벨이 금지된 경우 (매수 금지)
                            next_buy_target = None
                            next_buy_price = None
                            status = "sell_all_forbidden"
                        elif forbidden_num == 7:
                            # 금지 레벨 없음, B1이 목표
                            next_buy_target = "B1"
                            next_buy_price = buy_levels['B1']
                            status = "sell_no_forbidden_b1"
                        else:
                            # forbidden_num = 6이면 B1 금지, B2가 목표
                            # forbidden_num = 5이면 B1-B2 금지, B3이 목표
                            # forbidden_num = 1이면 B1-B6 금지, B7이 목표
                            # 공식: B{8 - forbidden_num}
                            next_buy_target = f"B{8 - forbidden_num}"
                            next_buy_price = buy_levels[next_buy_target]
                            status = f"sell_forbidden_next_{next_buy_target}"
                    else:
                        # forbidden 정보가 없으면 B1이 목표
                        next_buy_target = "B1"
                        next_buy_price = buy_levels['B1']
                        status = "sell_no_forbidden_b1"
                
                elif latest_event == 'RESTART_+98.5pct':
                    # RESTART 이벤트: 사이클 초기화로 B1이 목표
                    next_buy_target = "B1"
                    next_buy_price = buy_levels['B1']
                    status = "restart_b1_target"
                
                elif latest_event == 'STOP LOSS':
                    # STOP LOSS 이벤트: 손절 상태, 추가 매수 금지 (실행됨)
                    next_buy_target = "STOP LOSS (실행됨)"
                    next_buy_price = buy_levels['Stop_Loss'] if buy_levels['Stop_Loss'] is not None else h_value * 0.19
                    status = "level_stop_loss"
                
                else:
                    # 기타 이벤트: B1이 목표
                    next_buy_target = "B1"
                    next_buy_price = buy_levels['B1']
                    status = "other_event_b1_target"
            
            if next_buy_price is not None:
                distance_pct = ((current_price - next_buy_price) / next_buy_price) * 100
                return {
                    "status": status,
                    "next_buy_target": next_buy_target,
                    "next_buy_price": next_buy_price,
                    "current_price": current_price,
                    "h_value": h_value,
                    "buy_levels": buy_levels,
                    "distance_pct": distance_pct
                }
            else:
                return {"status": "no_target_price", "next_buy_target": None, "current_price": current_price, "h_value": h_value, "buy_levels": buy_levels}
            
        except Exception as e:
            print(f"{symbol} 매수 진행 상황 분석 실패: {e}")
            return {"status": "error", "next_buy_target": None, "current_price": None, "h_value": None}
    
    
    
    def format_market_cap(self, market_cap: float) -> str:
        """시가총액을 억 단위로 포맷팅"""
        if market_cap >= 1e8:  # 1억 이상
            return f"{market_cap / 1e8:,.1f}억"
        elif market_cap >= 1e4:  # 1만 이상
            return f"{market_cap / 1e4:,.1f}만"
        else:
            return f"{market_cap:,.0f}"
    
    def format_price(self, price: float, h_value: float = None) -> str:
        """가격을 천 단위 콤마로 포맷팅 (H값에 따라 소수점 자릿수 조정)"""
        if price is None:
            return ""
        
        # H값에 따라 소수점 자릿수 결정
        if h_value is not None:
            if h_value <= 1:
                return f"{price:,.6f}"
            elif h_value <= 10:
                return f"{price:,.4f}"
        
        return f"{price:,.2f}"
    
    def create_analysis_excel(self):
        """종합 분석 엑셀 파일 생성"""
        print("Top 100 코인 정보 수집 중...")
        coins = self.get_top100_coins_with_prices()
        
        if not coins:
            print("코인 정보를 가져올 수 없습니다.")
            return
            
        print(f"{len(coins)}개 코인 정보 수집 완료")
        
        # 분석 데이터 준비
        analysis_data = []
        
        for coin in coins:
            symbol = coin["심볼"]
            current_price = coin["현재가"]
            
            print(f"{symbol} 분석 중...")
            
            # 매수 진행 상황 분석
            buy_progress = self.get_latest_buy_progress(symbol)
            
            if buy_progress["status"] in ["no_debug_file", "empty_debug", "no_h_value", "error"]:
                print(f"  {symbol}: {buy_progress['status']}")
                analysis_data.append({
                    **coin,
                    "시가총액($)": self.format_market_cap(coin["시가총액"]),
                    "현재가": self.format_price(coin["현재가"]),
                    "H값": "",
                    "B1": "", "B2": "", "B3": "", "B4": "", 
                    "B5": "", "B6": "", "B7": "", "Stop_Loss": "",
                    "다음매수목표": "",
                    "목표가격": "",
                    "이격도(%)": None,
                    "상태": buy_progress["status"]
                })
                continue
            
            # 매수 진행 상황이 있는 경우
            h_value = buy_progress["h_value"]
            next_target = buy_progress["next_buy_target"]
            next_price = buy_progress["next_buy_price"]
            distance_pct = buy_progress["distance_pct"]
            buy_levels = buy_progress["buy_levels"]
            
            # DEBUG 파일에서 가져온 B1~B7, Stop_Loss 값 포맷팅
            formatted_buy_levels = {k: self.format_price(v, h_value) if v is not None else "" for k, v in buy_levels.items()}
            
            print(f"  {symbol}: H={h_value:.2f}, 현재가={current_price:.2f}, 다음목표={next_target}, 이격도={distance_pct:.1f}%")
            
            analysis_data.append({
                **coin,
                "시가총액($)": self.format_market_cap(coin["시가총액"]),
                "현재가": self.format_price(coin["현재가"], h_value),
                "H값": self.format_price(h_value, h_value),
                **formatted_buy_levels,
                "다음매수목표": next_target,
                "목표가격": self.format_price(next_price, h_value),
                "이격도(%)": distance_pct,
                "상태": buy_progress["status"]
            })
            
            # API 호출 제한 방지
            time.sleep(0.1)
        
        # DataFrame 생성
        df = pd.DataFrame(analysis_data)
        
        # 컬럼 순서 정리
        columns = [
            "순위", "코인명", "심볼", "시가총액($)", "현재가", "24h변동률",
            "H값", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "Stop_Loss",
            "다음매수목표", "목표가격", "이격도(%)", "상태"
        ]
        
        df = df[columns]
        
        # 엑셀 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = self.output_dir / f"coin_analysis_{timestamp}.xlsx"
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='코인분석', index=False)
            
            # 워크시트 포맷팅
            worksheet = writer.sheets['코인분석']
            
            # 백분율 형식 적용
            from openpyxl.styles import NamedStyle
            from openpyxl.styles.numbers import FORMAT_PERCENTAGE_00
            
            # 24h변동률 컬럼 (F열)에 백분율 형식 적용
            for row in range(2, len(df) + 2):  # 헤더 제외하고 데이터 행만
                cell = worksheet[f'F{row}']
                if cell.value != "" and cell.value is not None:
                    cell.number_format = '0.00"%"'  # 백분율 기호만 추가
            
            # 이격도(%) 컬럼 (R열)에 백분율 형식 적용
            for row in range(2, len(df) + 2):  # 헤더 제외하고 데이터 행만
                cell = worksheet[f'R{row}']
                if cell.value is not None:
                    cell.number_format = '0.00"%"'  # 백분율 기호만 추가
            
            # 컬럼 너비 조정
            column_widths = {
                'A': 8,   # 순위
                'B': 20,  # 코인명
                'C': 10,  # 심볼
                'D': 15,  # 시가총액
                'E': 12,  # 현재가
                'F': 12,  # 24h변동률
                'G': 12,  # H값
                'H': 10,  # B1
                'I': 10,  # B2
                'J': 10,  # B3
                'K': 10,  # B4
                'L': 10,  # B5
                'M': 10,  # B6
                'N': 10,  # B7
                'O': 12,  # Stop_Loss
                'P': 15,  # 다음매수목표
                'Q': 12,  # 목표가격
                'R': 10   # 이격도(%)
            }
            
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
        
        print(f"\n분석 완료! 엑셀 파일 저장: {excel_path}")
        print(f"총 {len(analysis_data)}개 코인 분석")
        
        # 요약 정보 출력
        valid_data = df.dropna(subset=['H값'])
        print(f"H값이 있는 코인: {len(valid_data)}개")
        
        if len(valid_data) > 0:
            # 이격도(%) 컬럼을 숫자로 변환 (빈 문자열은 NaN으로 처리)
            valid_data['이격도(%)'] = pd.to_numeric(valid_data['이격도(%)'], errors='coerce')
            avg_distance = valid_data['이격도(%)'].mean()
            print(f"평균 매수 목표 이격도: {avg_distance:.2f}%")
        
        return excel_path

def main():
    analyzer = CoinAnalysisExcel()
    analyzer.create_analysis_excel()

if __name__ == "__main__":
    main()
