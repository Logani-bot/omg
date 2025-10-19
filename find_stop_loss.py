import os
import glob
import pandas as pd

# DEBUG 파일들 찾기
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

# 결과 출력
print('STOP LOSS 발생 코인들:')
print('=' * 50)
for coin_info in stop_loss_coins:
    print(f'{coin_info["coin"]:8} - {coin_info["count"]}회 발생')
    for date in coin_info['dates']:
        print(f'          {date}')
    print()

print(f'총 {len(stop_loss_coins)}개 코인에서 STOP LOSS 발생')
