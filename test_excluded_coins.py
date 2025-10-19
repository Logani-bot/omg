import requests
import time

# 새로운 제외 설정 테스트
print("새로운 제외 설정 테스트")
print("=" * 60)

# 1. universe_selector.py의 새로운 제외 설정
print("\n1. universe_selector.py 새로운 제외 설정:")
print("-" * 40)

EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH", "USD1", "BFUSD", "BNSOL", "BNB", "ENA"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}

print("EXCLUDE_SYMBOLS:")
for symbol in sorted(EXCLUDE_SYMBOLS):
    print(f"  - {symbol}")

print("\nEXCLUDE_NAME_KEYWORDS:")
for keyword in EXCLUDE_NAME_KEYWORDS:
    print(f"  - {keyword}")

# 2. auto_debug_builder.py의 새로운 제외 설정
print("\n2. auto_debug_builder.py 새로운 제외 설정:")
print("-" * 40)

exclude_symbols = {
    "USDTUSDT", "USDCUSDT", "USDEUSDT", "USDSUSDT", "DAIUSDT",  # 스테이블코인
    "WBTCUSDT", "WBETHUSDT", "WEETHUSDT", "STETHUSDT", "WSTETHUSDT",  # 래핑 토큰
    "FIGR_HELOCUSDT", "HYPEUSDT", "LEOUSDT", "USDT0USDT", "SUSDEUSDT",  # API 에러
    "MUSDT", "OKBUSDT", "WLFIUSDT", "BGBUSDT", "MNTUSDT", "CROUSDT",  # 데이터 없음
    "USD1USDT", "BFUSDUSDT", "BNSOLUSDT", "BNBUSDT", "ENAUSDT"  # 추가 제외 코인
}

print("제외된 심볼들 (새로 추가된 것들):")
new_exclusions = ["USD1USDT", "BFUSDUSDT", "BNSOLUSDT", "BNBUSDT", "ENAUSDT"]
for symbol in new_exclusions:
    print(f"  - {symbol}")

# 3. 실제 CoinGecko에서 가져온 데이터로 테스트
print("\n3. CoinGecko Top 100 데이터로 제외 테스트:")
print("-" * 40)

def get_coingecko_data():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": False
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API 호출 실패: {response.status_code}")
            return None
    except Exception as e:
        print(f"API 호출 오류: {e}")
        return None

# CoinGecko 데이터 가져오기
data = get_coingecko_data()
if data:
    print(f"총 {len(data)}개 코인 데이터 수신")
    
    # 새로 제외된 코인들 확인
    newly_excluded = []
    still_included = []
    
    for coin in data:
        symbol = (coin.get("symbol") or "").upper() + "USDT"
        name = coin.get("name", "")
        rank = coin.get("market_cap_rank", 999)
        
        # 새로 제외된 코인들 확인
        if symbol in new_exclusions:
            newly_excluded.append({
                'rank': rank,
                'symbol': symbol,
                'name': name,
                'market_cap': coin.get('market_cap', 0)
            })
        elif symbol.replace("USDT", "") in ["USD1", "BFUSD", "BNSOL", "BNB", "ENA"]:
            still_included.append({
                'rank': rank,
                'symbol': symbol,
                'name': name,
                'market_cap': coin.get('market_cap', 0)
            })
    
    print(f"\n새로 제외된 코인: {len(newly_excluded)}개")
    if newly_excluded:
        print("새로 제외된 코인 목록:")
        for coin in sorted(newly_excluded, key=lambda x: x['rank']):
            print(f"  {coin['rank']:3}위: {coin['symbol']:15} ({coin['name']:20}) - 시총: ${coin['market_cap']:,.0f}")
    else:
        print("  (현재 Top 100에 해당 코인들이 없음)")
    
    print(f"\n아직 포함된 코인 (제외되어야 할): {len(still_included)}개")
    if still_included:
        print("아직 포함된 코인 목록:")
        for coin in sorted(still_included, key=lambda x: x['rank']):
            print(f"  {coin['rank']:3}위: {coin['symbol']:15} ({coin['name']:20}) - 시총: ${coin['market_cap']:,.0f}")
    else:
        print("  (모든 대상 코인들이 제외됨)")

else:
    print("CoinGecko 데이터를 가져올 수 없습니다.")

print("\n" + "=" * 60)
print("제외 설정 업데이트 완료!")
print("=" * 60)
