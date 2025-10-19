import requests
import time

# 현재 제외 설정 확인
print("현재 제외 설정 분석")
print("=" * 60)

# 1. universe_selector.py의 제외 설정
print("\n1. universe_selector.py 제외 설정:")
print("-" * 40)

EXCLUDE_SYMBOLS = {"WBTC", "WETH", "WBETH", "STETH", "WSTETH", "WEETH"}
EXCLUDE_NAME_KEYWORDS = {"WRAPPED", "BRIDGE"}

print("EXCLUDE_SYMBOLS:")
for symbol in EXCLUDE_SYMBOLS:
    print(f"  - {symbol}")

print("\nEXCLUDE_NAME_KEYWORDS:")
for keyword in EXCLUDE_NAME_KEYWORDS:
    print(f"  - {keyword}")

# 2. auto_debug_builder.py의 제외 설정
print("\n2. auto_debug_builder.py 제외 설정:")
print("-" * 40)

exclude_symbols = {
    "USDTUSDT", "USDCUSDT", "USDEUSDT", "USDSUSDT", "DAIUSDT",  # 스테이블코인
    "WBTCUSDT", "WBETHUSDT", "WEETHUSDT", "STETHUSDT", "WSTETHUSDT",  # 래핑 토큰
    "FIGR_HELOCUSDT", "HYPEUSDT", "LEOUSDT", "USDT0USDT", "SUSDEUSDT",  # API 에러
    "MUSDT", "OKBUSDT", "WLFIUSDT", "BGBUSDT", "MNTUSDT", "CROUSDT"  # 데이터 없음
}

print("제외된 심볼들:")
for symbol in sorted(exclude_symbols):
    print(f"  - {symbol}")

# 3. 실제 CoinGecko에서 가져온 데이터 확인
print("\n3. CoinGecko Top 100 실제 데이터 확인:")
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
    
    # 제외된 코인들 찾기
    excluded_coins = []
    included_coins = []
    
    for coin in data:
        symbol = (coin.get("symbol") or "").upper() + "USDT"
        name = coin.get("name", "")
        rank = coin.get("market_cap_rank", 999)
        
        # 제외 조건 확인
        is_excluded = False
        reason = ""
        
        if symbol in exclude_symbols:
            is_excluded = True
            reason = "exclude_symbols"
        elif symbol.replace("USDT", "") in EXCLUDE_SYMBOLS:
            is_excluded = True
            reason = "EXCLUDE_SYMBOLS"
        elif any(k in name.upper() for k in EXCLUDE_NAME_KEYWORDS):
            is_excluded = True
            reason = "EXCLUDE_NAME_KEYWORDS"
        
        if is_excluded:
            excluded_coins.append({
                'rank': rank,
                'symbol': symbol,
                'name': name,
                'reason': reason,
                'market_cap': coin.get('market_cap', 0)
            })
        else:
            included_coins.append({
                'rank': rank,
                'symbol': symbol,
                'name': name,
                'market_cap': coin.get('market_cap', 0)
            })
    
    print(f"\n제외된 코인: {len(excluded_coins)}개")
    print("제외된 코인 목록 (상위 20개):")
    for coin in sorted(excluded_coins, key=lambda x: x['rank'])[:20]:
        print(f"  {coin['rank']:3}위: {coin['symbol']:15} ({coin['name']:20}) - {coin['reason']}")
    
    print(f"\n포함된 코인: {len(included_coins)}개")
    print("포함된 코인 목록 (상위 20개):")
    for coin in sorted(included_coins, key=lambda x: x['rank'])[:20]:
        print(f"  {coin['rank']:3}위: {coin['symbol']:15} ({coin['name']:20})")
    
    # 카테고리별 분석
    print(f"\n4. 제외된 코인 카테고리 분석:")
    print("-" * 40)
    
    stablecoins = [c for c in excluded_coins if 'USDT' in c['symbol'] or 'USDC' in c['symbol'] or 'DAI' in c['symbol']]
    wrapped = [c for c in excluded_coins if 'W' in c['symbol'] or 'WRAPPED' in c['name'].upper()]
    exchange = [c for c in excluded_coins if any(x in c['name'].upper() for x in ['BINANCE', 'COINBASE', 'KRAKEN', 'OKX', 'KUCOIN'])]
    liquid_staking = [c for c in excluded_coins if any(x in c['name'].upper() for x in ['STETH', 'LIDO', 'STAKING', 'STAKE'])]
    
    print(f"스테이블코인: {len(stablecoins)}개")
    for coin in stablecoins[:5]:
        print(f"  - {coin['symbol']} ({coin['name']})")
    
    print(f"\n래핑/브리지 토큰: {len(wrapped)}개")
    for coin in wrapped[:5]:
        print(f"  - {coin['symbol']} ({coin['name']})")
    
    print(f"\n거래소 토큰: {len(exchange)}개")
    for coin in exchange[:5]:
        print(f"  - {coin['symbol']} ({coin['name']})")
    
    print(f"\n리퀴드 스테이킹: {len(liquid_staking)}개")
    for coin in liquid_staking[:5]:
        print(f"  - {coin['symbol']} ({coin['name']})")

else:
    print("CoinGecko 데이터를 가져올 수 없습니다.")
