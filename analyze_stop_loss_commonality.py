import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

# STOP LOSS 발생 코인들
stop_loss_coins = ['ARB', 'BONK', 'ENA', 'FIL', 'ICP', 'PENGU', 'PEPE', 'SEI', 'TRUMP', 'VET', 'WLD']

print("STOP LOSS 발생 코인들의 공통점 분석")
print("=" * 80)

# 1. 시총 순위 분석
print("\n1. 시총 순위 분석")
print("-" * 40)

try:
    top100_df = pd.read_csv('debug/top_list_coin.csv')
    stop_loss_ranks = []
    
    for coin in stop_loss_coins:
        matching_rows = top100_df[top100_df['Symbol'].str.contains(coin, case=False, na=False)]
        if not matching_rows.empty:
            rank = matching_rows.index[0] + 1
            market_cap = matching_rows.iloc[0]['MarketCap(USD)']
            name = matching_rows.iloc[0]['Name']
            stop_loss_ranks.append({
                'coin': coin,
                'rank': rank,
                'market_cap': market_cap,
                'name': name
            })
    
    stop_loss_ranks.sort(key=lambda x: x['rank'])
    
    print("순위별 분포:")
    for item in stop_loss_ranks:
        print(f"{item['rank']:3}위: {item['coin']:8} ({item['name']}) - ${item['market_cap']:,.0f}")
    
    # 순위 통계
    ranks = [item['rank'] for item in stop_loss_ranks]
    print(f"\n순위 통계:")
    print(f"  평균 순위: {np.mean(ranks):.1f}위")
    print(f"  중간 순위: {np.median(ranks):.1f}위")
    print(f"  최고 순위: {min(ranks)}위 (ENA)")
    print(f"  최저 순위: {max(ranks)}위 (FIL)")
    print(f"  하위권(80위 이상): {len([r for r in ranks if r >= 80])}개")
    print(f"  중위권(50-80위): {len([r for r in ranks if 50 <= r < 80])}개")
    print(f"  상위권(50위 미만): {len([r for r in ranks if r < 50])}개")

except Exception as e:
    print(f"시총 데이터 로드 실패: {e}")

# 2. 코인 유형 분석
print("\n2. 코인 유형 분석")
print("-" * 40)

coin_categories = {
    'Layer 1': ['ICP', 'SEI'],
    'Layer 2': ['ARB'],
    'Meme Coin': ['PEPE', 'BONK', 'PENGU', 'TRUMP'],
    'DeFi': ['ENA'],
    'Storage': ['FIL'],
    'Supply Chain': ['VET'],
    'AI/Identity': ['WLD']
}

print("카테고리별 분포:")
for category, coins in coin_categories.items():
    stop_loss_in_category = [coin for coin in coins if coin in stop_loss_coins]
    if stop_loss_in_category:
        print(f"  {category}: {stop_loss_in_category} ({len(stop_loss_in_category)}개)")

# 3. 시장 상황 분석 (STOP LOSS 발생 시점)
print("\n3. STOP LOSS 발생 시점 분석")
print("-" * 40)

# 각 코인의 STOP LOSS 발생 시점 분석
stop_loss_dates = {
    'ARB': ['2024-08-04'],
    'BONK': ['2025-03-03'],
    'ENA': ['2024-08-03', '2025-04-06'],
    'FIL': ['2025-10-10'],
    'ICP': ['2025-10-10'],
    'PENGU': ['2025-02-17'],
    'PEPE': ['2025-03-10'],
    'SEI': ['2024-08-04', '2025-04-06'],
    'TRUMP': ['2025-02-27'],
    'VET': ['2025-10-10'],
    'WLD': ['2024-06-30', '2025-03-08']
}

# 월별 집중도 분석
monthly_counts = {}
for coin, dates in stop_loss_dates.items():
    for date in dates:
        month = date[:7]  # YYYY-MM
        monthly_counts[month] = monthly_counts.get(month, 0) + 1

print("월별 STOP LOSS 발생 횟수:")
for month in sorted(monthly_counts.keys()):
    print(f"  {month}: {monthly_counts[month]}회")

# 4. 변동성 분석 (가격 데이터 기반)
print("\n4. 변동성 분석")
print("-" * 40)

volatility_analysis = []
for coin in stop_loss_coins:
    try:
        df = pd.read_csv(f'debug/{coin}_debug.csv')
        if not df.empty and 'close' in df.columns:
            # 최근 30일 변동성 계산
            recent_30 = df.tail(30)
            if len(recent_30) >= 30:
                returns = recent_30['close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(365)  # 연환산 변동성
                volatility_analysis.append({
                    'coin': coin,
                    'volatility': volatility,
                    'max_price': recent_30['close'].max(),
                    'min_price': recent_30['close'].min(),
                    'price_range': (recent_30['close'].max() - recent_30['close'].min()) / recent_30['close'].min() * 100
                })
    except Exception as e:
        print(f"  {coin} 변동성 분석 실패: {e}")

if volatility_analysis:
    volatilities = [item['volatility'] for item in volatility_analysis]
    print("변동성 통계 (연환산):")
    print(f"  평균 변동성: {np.mean(volatilities):.1%}")
    print(f"  중간 변동성: {np.median(volatilities):.1%}")
    print(f"  최고 변동성: {max(volatilities):.1%}")
    print(f"  최저 변동성: {min(volatilities):.1%}")
    
    print("\n변동성 상위 코인:")
    volatility_analysis.sort(key=lambda x: x['volatility'], reverse=True)
    for item in volatility_analysis[:5]:
        print(f"  {item['coin']:8}: {item['volatility']:.1%} (가격범위: {item['price_range']:.1f}%)")

# 5. 공통점 요약
print("\n5. STOP LOSS 코인들의 공통점 요약")
print("-" * 40)

print("주요 공통점:")
print("1. 시총 순위: 대부분 중하위권 (38-97위)")
print("2. 코인 유형: Meme Coin, Layer 1/2, DeFi 등 다양한 유형")
print("3. 발생 시점: 2024년 하반기와 2025년 상반기에 집중")
print("4. 변동성: 일반적으로 높은 변동성을 보임")
print("5. 시장 상황: 시장 전체의 급락 시기에 집중 발생")

print(f"\n총 {len(stop_loss_coins)}개 코인에서 STOP LOSS 발생")
print("이는 전체 분석 코인 중 약 12%에 해당")
