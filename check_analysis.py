#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

# ANALYSIS 파일 읽기
df = pd.read_excel('output/coin_analysis_20251019_224807.xlsx')

print("=== ANALYSIS 파일 컬럼 ===")
print(df.columns.tolist())

print("\n=== B7까지 완료된 코인들 (STOP LOSS 상태) ===")
stop_loss_df = df[df['다음매수목표'] == 'STOP LOSS']
print(f"총 {len(stop_loss_df)}개 코인")
print(stop_loss_df[['코인명', '심볼', '다음매수목표', '목표가격']].head(10))

print("\n=== B7까지 완료된 코인들 (STOP LOSS 대기 상태) ===")
b7_complete_df = df[df['다음매수목표'] == 'STOP LOSS']
print(f"총 {len(b7_complete_df)}개 코인")
print(b7_complete_df[['코인명', '심볼', 'H값', 'B7', 'Stop_Loss', '다음매수목표', '목표가격']].head(10))

print("\n=== 샘플 데이터 (처음 5개) ===")
print(df[['코인명', '심볼', 'H값', 'B7', 'Stop_Loss', '다음매수목표', '목표가격']].head())
