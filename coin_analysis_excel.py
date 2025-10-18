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

# 매수선 비율 (H값에서 빠진 비율)
BUY_LEVEL_RATIOS = [0.44, 0.48, 0.54, 0.59, 0.65, 0.72, 0.79]

# 제외할 심볼들 (래핑된 토큰)
EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}

class CoinAnalysisExcel:
    def __init__(self):
        self.output_dir = pathlib.Path("output")
        self.state_dir = pathlib.Path("debug")  # debug 폴더의 디버그 파일 사용
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_top30_coins_with_prices(self) -> List[Dict]:
        """CoinGecko에서 Top 50 코인 정보와 현재가를 가져옴"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 50,
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
                
                # Top 50개까지만
                if len(coins) >= 50:
                    break
            
            return coins
            
        except Exception as e:
            print(f"코인 정보 수집 실패: {e}")
            return []
    
    def get_latest_h_value(self, symbol: str) -> Optional[float]:
        """디버그 파일에서 가장 최근 일자의 H값을 가져옴"""
        debug_file = self.state_dir / f"{symbol}_debug.csv"
        
        if not debug_file.exists():
            return None
            
        try:
            df = pd.read_csv(debug_file)
            if df.empty:
                return None
                
            # H 컬럼에서 유효한 값 중 가장 최근 값 찾기
            if 'H' in df.columns:
                h_values = df['H'].dropna()
                if not h_values.empty:
                    return float(h_values.iloc[-1])
            
            # H값이 없으면 최근 high 값들의 최대값을 사용
            if 'high' in df.columns:
                recent_highs = df['high'].tail(30)  # 최근 30일
                if not recent_highs.empty:
                    return float(recent_highs.max())
                    
            return None
            
        except Exception as e:
            print(f"{symbol} H값 추출 실패: {e}")
            return None
    
    def calculate_buy_levels(self, h_value: float) -> Dict[str, float]:
        """H값에서 매수선들을 계산"""
        buy_levels = {}
        for i, ratio in enumerate(BUY_LEVEL_RATIOS, 1):
            level_price = h_value * (1 - ratio)
            buy_levels[f"B{i}"] = level_price
            
        return buy_levels
    
    def find_closest_buy_level(self, current_price: float, buy_levels: Dict[str, float]) -> Tuple[str, float, float]:
        """현재가보다 낮은 매수선 중 가장 큰 금액과 거리 계산"""
        valid_levels = {k: v for k, v in buy_levels.items() if v < current_price}
        
        if not valid_levels:
            return "", 0.0, 0.0
            
        # 가장 큰 금액의 매수선 찾기
        closest_level = max(valid_levels.items(), key=lambda x: x[1])
        level_name, level_price = closest_level
        
        # 거리 계산 (%)
        distance_pct = ((current_price - level_price) / level_price) * 100
        
        return level_name, level_price, distance_pct
    
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
        print("Top 50 코인 정보 수집 중...")
        coins = self.get_top30_coins_with_prices()
        
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
            
            # H값 가져오기
            h_value = self.get_latest_h_value(symbol)
            
            if h_value is None:
                print(f"  {symbol}: H값 없음")
                analysis_data.append({
                    **coin,
                    "시가총액": self.format_market_cap(coin["시가총액"]),  # 억 단위로 포맷팅
                    "현재가": self.format_price(coin["현재가"]),  # 콤마 포맷팅
                    "H값": "",
                    "B1": "", "B2": "", "B3": "", "B4": "", 
                    "B5": "", "B6": "", "B7": "",
                    "가장가까운매수선": "",
                    "매수선가격": "",
                    "거리(%)": None
                })
                continue
            
            # 매수선 계산
            buy_levels = self.calculate_buy_levels(h_value)
            
            # 가장 가까운 매수선 찾기
            closest_level, level_price, distance = self.find_closest_buy_level(
                current_price, buy_levels
            )
            
            print(f"  {symbol}: H={h_value:.2f}, 현재가={current_price:.2f}, 가장가까운={closest_level}")
            
            # 매수선들을 콤마 포맷팅 (H값에 따라 소수점 자릿수 조정)
            formatted_buy_levels = {k: self.format_price(v, h_value) for k, v in buy_levels.items()}
            
            analysis_data.append({
                **coin,
                "시가총액": self.format_market_cap(coin["시가총액"]),  # 억 단위로 포맷팅
                "현재가": self.format_price(coin["현재가"], h_value),  # H값에 따라 소수점 조정
                "H값": self.format_price(h_value, h_value),  # H값에 따라 소수점 조정
                **formatted_buy_levels,
                "가장가까운매수선": closest_level,
                "매수선가격": self.format_price(level_price, h_value),  # H값에 따라 소수점 조정
                "거리(%)": distance if distance else None  # 숫자(float)로 저장
            })
            
            # API 호출 제한 방지
            time.sleep(0.1)
        
        # DataFrame 생성
        df = pd.DataFrame(analysis_data)
        
        # 컬럼 순서 정리
        columns = [
            "순위", "코인명", "심볼", "시가총액", "현재가", "24h변동률",
            "H값", "B1", "B2", "B3", "B4", "B5", "B6", "B7",
            "가장가까운매수선", "매수선가격", "거리(%)"
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
            
            # 거리(%) 컬럼 (Q열)에 백분율 형식 적용
            for row in range(2, len(df) + 2):  # 헤더 제외하고 데이터 행만
                cell = worksheet[f'Q{row}']
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
                'O': 15,  # 가장가까운매수선
                'P': 12,  # 매수선가격
                'Q': 10   # 거리(%)
            }
            
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
        
        print(f"\n분석 완료! 엑셀 파일 저장: {excel_path}")
        print(f"총 {len(analysis_data)}개 코인 분석")
        
        # 요약 정보 출력
        valid_data = df.dropna(subset=['H값'])
        print(f"H값이 있는 코인: {len(valid_data)}개")
        
        if len(valid_data) > 0:
            # 거리(%) 컬럼을 숫자로 변환 (빈 문자열은 NaN으로 처리)
            valid_data['거리(%)'] = pd.to_numeric(valid_data['거리(%)'], errors='coerce')
            avg_distance = valid_data['거리(%)'].mean()
            print(f"평균 매수선 거리: {avg_distance:.2f}%")
        
        return excel_path

def main():
    analyzer = CoinAnalysisExcel()
    analyzer.create_analysis_excel()

if __name__ == "__main__":
    main()
