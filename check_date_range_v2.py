import os
import glob
import pandas as pd
from datetime import datetime

# DEBUG 파일들에서 날짜 범위 확인
debug_files = glob.glob('debug/*_debug.csv')

if not debug_files:
    print("DEBUG 파일을 찾을 수 없습니다.")
    exit()

print("DEBUG 파일들의 날짜 범위 분석")
print("=" * 60)

all_dates = []
file_count = 0
valid_files = 0

for file in debug_files:
    try:
        df = pd.read_csv(file)
        if 'date' in df.columns and not df.empty:
            # 날짜 컬럼을 datetime으로 변환
            df['date'] = pd.to_datetime(df['date'])
            dates = df['date'].tolist()
            all_dates.extend(dates)
            valid_files += 1
            
            if file_count < 5:  # 처음 5개 파일만 상세 출력
                coin_name = os.path.basename(file).replace('_debug.csv', '')
                min_date = df['date'].min()
                max_date = df['date'].max()
                row_count = len(df)
                print(f"{coin_name:8}: {min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')} ({row_count}일)")
            
            file_count += 1
    except Exception as e:
        print(f"Error processing {file}: {e}")

print(f"\n처리된 파일: {valid_files}개")

if all_dates:
    all_dates = pd.Series(all_dates)
    min_date = all_dates.min()
    max_date = all_dates.max()
    total_days = (max_date - min_date).days + 1
    
    print(f"\n전체 날짜 범위:")
    print(f"시작일: {min_date.strftime('%Y-%m-%d')}")
    print(f"종료일: {max_date.strftime('%Y-%m-%d')}")
    print(f"총 기간: {total_days}일")
    print(f"년도 범위: {min_date.year}년 ~ {max_date.year}년")
    
    # 년도별 데이터 분포
    print(f"\n년도별 데이터 분포:")
    year_counts = all_dates.dt.year.value_counts().sort_index()
    for year, count in year_counts.items():
        print(f"{year}년: {count:,}개 데이터")
    
    # 월별 데이터 분포 (최근 2년)
    recent_dates = all_dates[all_dates >= '2023-01-01']
    if not recent_dates.empty:
        print(f"\n월별 데이터 분포 (2023년 이후):")
        month_counts = recent_dates.dt.to_period('M').value_counts().sort_index()
        for month, count in month_counts.items():
            print(f"{month}: {count:,}개 데이터")

else:
    print("유효한 날짜 데이터를 찾을 수 없습니다.")
