import requests
import json
from datetime import datetime

class SlackNotifier:
    def __init__(self, webhook_url):
        """
        SlackNotifier 초기화
        Args:
            webhook_url (str): Slack Incoming Webhook URL
        """
        self.webhook_url = webhook_url

    def send_message(self, message, color="#36a64f"):
        """
        Slack으로 메시지 전송
        Args:
            message (str): 전송할 메시지
            color (str): 메시지 색상 (기본값: 초록색)
        Returns:
            bool: 전송 성공 여부
        """
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*{message}*"
                                }
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"🕒 {current_time}"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"Slack 메시지 전송 실패: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"Slack 메시지 전송 중 오류 발생: {str(e)}")
            return False

    def send_trade_signal(self, trade_type, stock_code, stock_name, price, quantity):
        """
        매매 신호 전송
        Args:
            trade_type (str): '매수' 또는 '매도'
            stock_code (str): 종목 코드
            stock_name (str): 종목명
            price (float): 가격
            quantity (int): 수량
        """
        emoji = "🔵" if trade_type == "매수" else "🔴"
        color = "#36a64f" if trade_type == "매수" else "#ff4444"
        
        message = (
            f"{emoji} {trade_type} 신호\n"
            f"• 종목: {stock_name} ({stock_code})\n"
            f"• 가격: {price:,}원\n"
            f"• 수량: {quantity:,}주\n"
            f"• 총액: {price * quantity:,}원"
        )
        
        return self.send_message(message, color)

    def send_error(self, error_message):
        """
        에러 메시지 전송
        Args:
            error_message (str): 에러 메시지
        """
        return self.send_message(f"⚠️ 오류 발생\n{error_message}", "#ff0000")

    def send_balance_update(self, balance_data):
        """
        잔고 업데이트 정보 전송
        Args:
            balance_data (list): 잔고 정보 리스트
        """
        if not balance_data:
            return self.send_message("💰 보유 종목 없음")

        message = "💰 잔고 현황\n"
        total_eval_amount = 0
        total_profit_loss = 0

        for item in balance_data:
            profit_rate = float(item.get('손익률', '0').replace('%', ''))
            eval_amount = int(item.get('평가금액', '0').replace(',', ''))
            
            message += (
                f"• {item['종목명']}\n"
                f"  수량: {item['보유수량']}주 | 평가금액: {eval_amount:,}원 | 손익률: {profit_rate}%\n"
            )
            
            total_eval_amount += eval_amount
            total_profit_loss += eval_amount * (profit_rate / 100)

        message += f"\n📊 총평가금액: {total_eval_amount:,}원"
        message += f"\n📈 총평가손익: {total_profit_loss:,.0f}원"
        
        color = "#36a64f" if total_profit_loss >= 0 else "#ff4444"
        return self.send_message(message, color)

def main():
    """
    SlackNotifier 사용 예제
    """
    # Slack Webhook URL 설정
    WEBHOOK_URL = "https://hooks.slack.com/services/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"  # 실제 사용시 이 부분을 본인의 Webhook URL로 교체하세요
    
    # SlackNotifier 인스턴스 생성
    notifier = SlackNotifier(WEBHOOK_URL)
    
    # 1. 기본 메시지 전송 예제
    print("\n1. 기본 메시지 전송")
    notifier.send_message("안녕하세요! 이것은 테스트 메시지입니다.")
    
    # 2. 컬러가 지정된 메시지 전송 예제
    print("\n2. 컬러 메시지 전송")
    notifier.send_message("이것은 파란색 메시지입니다.", color="#0000FF")
    
    # 3. 매수 신호 전송 예제
    print("\n3. 매수 신호 전송")
    notifier.send_trade_signal(
        trade_type="매수",
        stock_code="005930",
        stock_name="삼성전자",
        price=70000,
        quantity=10
    )
    
    # 4. 매도 신호 전송 예제
    print("\n4. 매도 신호 전송")
    notifier.send_trade_signal(
        trade_type="매도",
        stock_code="005930",
        stock_name="삼성전자",
        price=71000,
        quantity=10
    )
    
    # 5. 에러 메시지 전송 예제
    print("\n5. 에러 메시지 전송")
    notifier.send_error("API 연결 중 타임아웃이 발생했습니다.")
    
    # 6. 잔고 업데이트 전송 예제
    print("\n6. 잔고 업데이트 전송")
    balance_data = [
        {
            "종목명": "삼성전자",
            "종목코드": "005930",
            "보유수량": "100",
            "평가금액": "7,000,000",
            "손익률": "5.5%"
        },
        {
            "종목명": "NAVER",
            "종목코드": "035420",
            "보유수량": "20",
            "평가금액": "6,000,000",
            "손익률": "-2.3%"
        }
    ]
    notifier.send_balance_update(balance_data)

if __name__ == "__main__":
    # 사용 방법 출력
    print("""
SlackNotifier 사용 예제를 실행합니다.
실행하기 전에 다음 사항을 확인하세요:
1. WEBHOOK_URL 변수에 실제 Slack Webhook URL을 입력했는지 확인
2. 인터넷 연결 상태 확인
    """)
    
    # 사용자 확인 후 실행
    input("계속하려면 Enter를 누르세요...")
    main()
