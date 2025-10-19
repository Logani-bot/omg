import os
import glob
import pandas as pd

# DEBUG 파일들에서 STOP LOSS 발생 코인 찾기
debug_files = glob.glob('debug/*_debug.csv')
stop_loss_coins = []

for file in debug_files:
    try:
        df = pd.read_csv(file)
        # STOP LOSS 이벤트가 있는지 확인
        stop_loss_events = df[df['event'] == 'STOP LOSS']
        if not stop_loss_events.empty:
            coin_name = os.path.basename(file).replace('_debug.csv', '')
            stop_loss_count = len(stop_loss_events)
            stop_loss_dates = stop_loss_events['date'].tolist()
            stop_loss_coins.append({
                'coin': coin_name,
                'count': stop_loss_count,
                'dates': stop_loss_dates
            })
    except Exception as e:
        print(f'Error processing {file}: {e}')

# TOP100 리스트에서 시총 순위 가져오기
try:
    top100_df = pd.read_csv('debug/top_list_coin.csv')
    print("TOP100 리스트 로드 성공")
    print(f"총 {len(top100_df)}개 코인")
    print("\n컬럼명:", top100_df.columns.tolist())
    print("\n첫 5행:")
    print(top100_df.head())
except Exception as e:
    print(f"TOP100 리스트 로드 실패: {e}")
    top100_df = None

# STOP LOSS 코인들의 시총 순위 매칭
print('\n' + '='*80)
print('STOP LOSS 발생 코인들의 시총 순위 분석')
print('='*80)

if top100_df is not None:
    # 심볼 컬럼 찾기 (다양한 가능성 고려)
    symbol_col = None
    for col in ['Symbol', 'symbol', '심볼', 'SYMBOL']:
        if col in top100_df.columns:
            symbol_col = col
            break
    
    if symbol_col:
        print(f"심볼 컬럼: {symbol_col}")
        
        # STOP LOSS 코인들의 순위 찾기
        for coin_info in stop_loss_coins:
            coin_name = coin_info['coin']
            
            # 심볼 매칭 (USDT 제거 등)
            matching_rows = top100_df[top100_df[symbol_col].str.contains(coin_name, case=False, na=False)]
            
            if not matching_rows.empty:
                rank = matching_rows.index[0] + 1  # 0-based index를 1-based로 변환
                market_cap = matching_rows.iloc[0].get('Market Cap', 'N/A')
                print(f"{rank:3}위 - {coin_name:8} ({coin_info['count']}회 STOP LOSS)")
                print(f"      시총: {market_cap}")
                for date in coin_info['dates']:
                    print(f"      발생일: {date}")
                print()
            else:
                print(f"순위미상 - {coin_name:8} ({coin_info['count']}회 STOP LOSS)")
                for date in coin_info['dates']:
                    print(f"      발생일: {date}")
                print()
    else:
        print("심볼 컬럼을 찾을 수 없습니다.")
        print("사용 가능한 컬럼:", top100_df.columns.tolist())
else:
    print("TOP100 데이터를 사용할 수 없습니다.")
    for coin_info in stop_loss_coins:
        print(f"{coin_info['coin']:8} - {coin_info['count']}회 발생")
        for date in coin_info['dates']:
            print(f"          {date}")
        print()

print(f'\n총 {len(stop_loss_coins)}개 코인에서 STOP LOSS 발생')
