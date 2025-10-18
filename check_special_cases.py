#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd

# 최신 analysis 파일 읽기
df = pd.read_excel('output/coin_analysis_20251018_190405.xlsx')

print("=== 특이사항 있는 코인들 ===")
print()

print("1. SELL 이벤트로 인한 높은 레벨 목표 (B6, B7):")
sell_cases = df[df['다음매수목표'].isin(['B6', 'B7'])]
if not sell_cases.empty:
    print(sell_cases[['코인명', '심볼', '다음매수목표', '목표가격', '이격도(%)', '상태']].to_string(index=False))
else:
    print("해당하는 코인이 없습니다.")
print()

print("2. 음수 이격도 (현재가가 목표가보다 높음):")
neg_cases = df[df['이격도(%)'] < 0]
if not neg_cases.empty:
    print(neg_cases[['코인명', '심볼', '다음매수목표', '목표가격', '이격도(%)', '상태']].to_string(index=False))
else:
    print("해당하는 코인이 없습니다.")
print()

print("3. 매우 높은 이격도 (50% 이상):")
high_cases = df[df['이격도(%)'] > 50]
if not high_cases.empty:
    print(high_cases[['코인명', '심볼', '다음매수목표', '목표가격', '이격도(%)', '상태']].to_string(index=False))
else:
    print("해당하는 코인이 없습니다.")
print()

print("4. 매수 금지 상태:")
forbidden_cases = df[df['상태'] == 'sell_all_forbidden']
if not forbidden_cases.empty:
    print(forbidden_cases[['코인명', '심볼', '다음매수목표', '목표가격', '이격도(%)', '상태']].to_string(index=False))
else:
    print("해당하는 코인이 없습니다.")
print()

print("5. B2 목표인 코인들 (SELL 이벤트 후):")
b2_cases = df[df['다음매수목표'] == 'B2']
if not b2_cases.empty:
    print(f"총 {len(b2_cases)}개 코인:")
    print(b2_cases[['코인명', '심볼', '다음매수목표', '목표가격', '이격도(%)', '상태']].to_string(index=False))
else:
    print("해당하는 코인이 없습니다.")
