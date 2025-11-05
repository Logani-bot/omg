"""
Slack 알람 전송 모듈
"""
import os
import requests
import logging
from typing import Optional
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Slack Webhook URL
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def _send_slack_message(message: str, parse_html: bool = True, blocks: list = None) -> bool:
    """
    Slack 메시지 전송 (Incoming Webhook 사용)
    
    Args:
        message: 전송할 메시지 (HTML 태그 포함 가능) - fallback 텍스트로 사용
        parse_html: HTML 태그를 Slack 마크다운으로 변환할지 여부
        blocks: Block Kit blocks 배열 (있으면 blocks 사용, 없으면 text 사용)
    
    Returns:
        bool: 전송 성공 여부
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack Webhook URL이 설정되지 않았습니다. Slack 알림을 건너뜁니다.")
        return False
    
    try:
        if blocks:
            # Block Kit 형식 사용
            payload = {
                "text": message,  # fallback 텍스트
                "blocks": blocks
            }
        else:
            # 일반 텍스트 형식
            if parse_html:
                slack_message = convert_html_to_slack_markdown(message)
            else:
                slack_message = message
            
            payload = {
                "text": slack_message
            }
        
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info("✓ Slack 전송 성공")
        return True
    
    except Exception as e:
        logger.error(f"✗ Slack 전송 실패: {e}")
        return False


def convert_html_to_slack_markdown(html_text: str) -> str:
    """
    HTML 태그를 Slack 마크다운으로 변환
    
    Args:
        html_text: HTML 형식의 텍스트
    
    Returns:
        str: Slack 마크다운 형식의 텍스트
    """
    import re
    
    # <b>태그 → *bold*
    text = re.sub(r'<b>(.*?)</b>', r'*\1*', html_text)
    
    # <tg-spoiler>태그 → _spoiler_ (이탤릭체로)
    text = re.sub(r'<tg-spoiler>(.*?)</tg-spoiler>', r'_\1_', text)
    
    # <pre>태그 → ```code block```
    text = re.sub(r'<pre>(.*?)</pre>', r'```\1```', text, flags=re.DOTALL)
    
    # HTML 엔티티 디코딩
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    
    # 이모지는 그대로 유지
    return text


def format_price(price: float, h_value: float = None) -> str:
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


def get_sell_threshold(buy_level: str) -> Optional[float]:
    """매수 레벨에 따른 매도 기준 퍼센트 반환"""
    sell_thresholds = {
        'B1': 7.7,
        'B2': 17.3,
        'B3': 24.4,
        'B4': 37.4,
        'B5': 52.7,
        'B6': 79.9,
        'B7': 98.5
    }
    return sell_thresholds.get(buy_level)


def _send_slack_alert(alert_data: dict) -> bool:
    """
    매수 목표 접근 알림을 Slack으로 전송 (Block Kit 형식)
    
    Args:
        alert_data: 알림 데이터 딕셔너리
    
    Returns:
        bool: 전송 성공 여부
    """
    try:
        # 가격 포맷팅 (H값 기반)
        h_value = alert_data.get('h_value', 0)
        current_price_str = format_price(alert_data['current_price'], h_value)
        target_price_str = format_price(alert_data['target_price'], h_value)
        h_value_str = format_price(h_value, h_value)
        
        # 매도 기준 퍼센트 가져오기
        sell_threshold = get_sell_threshold(alert_data['target'])
        sell_criteria_text = ""
        if sell_threshold:
            sell_criteria_text = f"\n매도 기준: +{sell_threshold}%"
        
        # 첫 자리 여부 확인
        is_first = alert_data.get('is_first', False)
        
        # Block Kit blocks 생성
        blocks = []
        
        # Header
        header_text = "✅ 매수 목표 접근 알림"
        if is_first:
            header_text = "✅ 매수 목표 접근 알림 (첫 자리)"
        
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
                "emoji": True
            }
        })
        
        # Context (Reference High)
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Reference High :* ${h_value_str}"
                }
            ]
        })
        
        # Rich Text (코인 정보) - 정렬된 형식
        coin_name = f"{alert_data.get('name', '')} ({alert_data.get('symbol', '')})"
        rank = str(alert_data['rank'])
        target_info = f"{alert_data['target']} - ${target_price_str}"
        if sell_criteria_text:
            # 매도기준을 별도 줄로 분리
            sell_info = sell_criteria_text.replace("\n매도 기준: ", "").replace("+", "").replace("%", "")
            coin_info_text = (
                f"코인명     : {coin_name}\n"
                f"시총 순위   : {rank}\n\n"
                f"현재가     : ${current_price_str}\n"
                f"매수 목표   : {target_info}\n"
                f"매도 기준   : +{sell_info}%\n"
                f"이격도     : {alert_data['divergence']:.2f}%"
            )
        else:
            coin_info_text = (
                f"코인명     : {coin_name}\n"
                f"시총 순위   : {rank}\n\n"
                f"현재가     : ${current_price_str}\n"
                f"매수 목표   : {target_info}\n"
                f"이격도     : {alert_data['divergence']:.2f}%"
            )
        
        blocks.append({
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_preformatted",
                    "elements": [
                        {
                            "type": "text",
                            "text": coin_info_text
                        }
                    ]
                }
            ]
        })
        
        # Actions (Bybit 버튼)
        symbol = alert_data.get('symbol', '')
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📈 Open Bybit"
                    },
                    "url": f"bybitapp://trade/{symbol}USDT",
                    "action_id": "open_bybit_app"
                }
            ]
        })
        
        # Divider
        blocks.append({
            "type": "divider"
        })
        
        # Fallback 텍스트
        fallback_text = f"매수 목표 접근 알림: {alert_data.get('name', '')} ({alert_data.get('symbol', '')})"
        
        return _send_slack_message(fallback_text, parse_html=False, blocks=blocks)
        
    except Exception as e:
        logger.error(f"Slack 알림 포맷팅 실패: {e}")
        return False


def _send_slack_buy_execution_alert(execution_data: dict, price_data: dict, current_price: Optional[float]) -> bool:
    """
    매수 실행 알림을 Slack으로 전송 (Block Kit 형식)
    
    Args:
        execution_data: 실행 데이터 딕셔너리
        price_data: 가격 데이터 딕셔너리 (avg_buy_price, sell_price, sell_threshold 등)
        current_price: 현재가 (Optional)
    
    Returns:
        bool: 전송 성공 여부
    """
    try:
        # 가격 포맷팅 (H값 기반)
        h_value = execution_data.get('h_value', 0)
        current_price_str = f"${format_price(current_price, h_value)}" if current_price else "조회실패"
        target_price_str = format_price(execution_data['target_price'], h_value)
        candle_low_str = format_price(execution_data['candle_low'], h_value)
        avg_buy_price_str = format_price(price_data['avg_buy_price'], h_value)
        sell_price_str = format_price(price_data['sell_price'], h_value)
        
        # Block Kit blocks 생성
        blocks = []
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 매수 실행 알림",
                "emoji": True
            }
        })
        
        # Section (코인 정보) - 정렬된 형식
        section_text = (
            f"*코인명     :* {execution_data['name']} ({execution_data['symbol']})\n"
            f"*시총 순위   :* {execution_data['rank']}\n\n"
            f"*매수 목표   :* {execution_data['target']} — ${target_price_str}\n"
            f"*5분봉 저가 :* ${candle_low_str}\n\n"
            f"*현재가     :* {current_price_str}\n"
            f"*평균매수가 :* ${avg_buy_price_str}\n"
            f"*예상 매도가 :* ${sell_price_str} (+{price_data['sell_threshold']:.1f}%)"
        )
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": section_text
            }
        })
        
        # Divider
        blocks.append({
            "type": "divider"
        })
        
        # Fallback 텍스트
        fallback_text = f"매수 실행 알림: {execution_data['name']} ({execution_data['symbol']})"
        
        return _send_slack_message(fallback_text, parse_html=False, blocks=blocks)
        
    except Exception as e:
        logger.error(f"Slack 매수 실행 알림 포맷팅 실패: {e}")
        return False


# Slack Webhook URL이 없으면 함수들을 None으로 설정
if not SLACK_WEBHOOK_URL:
    logger.info("Slack Webhook URL이 설정되지 않았습니다. Slack 알림 기능을 비활성화합니다.")
    send_slack_alert = None
    send_slack_buy_execution_alert = None
    send_slack_message = None
else:
    # 함수들을 export
    send_slack_message = _send_slack_message
    send_slack_alert = _send_slack_alert
    send_slack_buy_execution_alert = _send_slack_buy_execution_alert


# 테스트용
if __name__ == "__main__":
    # 간단한 테스트 메시지
    test_msg = "🤖 *Slack 봇 테스트*\n테스트 메시지입니다!"
    
    print("Slack 테스트 메시지 전송 중...")
    if send_slack_message:
        send_slack_message(test_msg, parse_html=False)
    else:
        print("Slack Webhook URL이 설정되지 않았습니다.")
