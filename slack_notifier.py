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


def _send_slack_message(message: str, parse_html: bool = True) -> bool:
    """
    Slack 메시지 전송 (Incoming Webhook 사용)
    
    Args:
        message: 전송할 메시지 (HTML 태그 포함 가능)
        parse_html: HTML 태그를 Slack 마크다운으로 변환할지 여부
    
    Returns:
        bool: 전송 성공 여부
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning("Slack Webhook URL이 설정되지 않았습니다. Slack 알림을 건너뜁니다.")
        return False
    
    try:
        # HTML 태그를 Slack 마크다운으로 변환
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


def _send_slack_alert(alert_data: dict) -> bool:
    """
    매수 목표 접근 알림을 Slack으로 전송
    
    Args:
        alert_data: 알림 데이터 딕셔너리
    
    Returns:
        bool: 전송 성공 여부
    """
    try:
        message = (
            f"🪙 *매수 목표 접근 알림*\n"
            f"────────────\n"
            f"코인명: {alert_data['name']} ({alert_data['symbol']})\n"
            f"시총 순위: {alert_data['rank']}\n\n"
            f"현재가: ${alert_data['current_price']:,.4f}\n"
            f"매수목표: *{alert_data['target']} - ${alert_data['target_price']:,.4f}*\n"
            f"이격도: *{alert_data['divergence']:.2f}%*\n"
            f"────────────\n"
            f"_* 기준 고점: ${alert_data['h_value']:,.2f}_"
        )
        
        return _send_slack_message(message, parse_html=False)
        
    except Exception as e:
        logger.error(f"Slack 알림 포맷팅 실패: {e}")
        return False


def _send_slack_buy_execution_alert(execution_data: dict, price_data: dict, current_price: Optional[float]) -> bool:
    """
    매수 실행 알림을 Slack으로 전송
    
    Args:
        execution_data: 실행 데이터 딕셔너리
        price_data: 가격 데이터 딕셔너리 (avg_buy_price, sell_price, sell_threshold 등)
        current_price: 현재가 (Optional)
    
    Returns:
        bool: 전송 성공 여부
    """
    try:
        current_price_str = f"${current_price:,.2f}" if current_price else "조회실패"
        
        message = (
            f"⚡ *매수 실행 알림*\n"
            f"────────────\n"
            f"코인명: {execution_data['name']} ({execution_data['symbol']})\n"
            f"시총 순위: {execution_data['rank']}\n\n"
            f"매수 목표: {execution_data['target']} — ${execution_data['target_price']:,.2f}\n"
            f"5분봉 저가: ${execution_data['candle_low']:,.2f}\n\n"
            f"현재가: ${current_price:,.2f}\n"
            f"평균매수가: ${price_data['avg_buy_price']:,.2f}\n"
            f"예상 매도가: ${price_data['sell_price']:,.2f} (+{price_data['sell_threshold']:.1f}%)\n"
            f"────────────\n"
            f"_* 기준 고점: ${execution_data['h_value']:,.2f}_"
        )
        
        return _send_slack_message(message, parse_html=False)
        
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

