import json

class Config:
    def __init__(self, path="config.json"):
        self.config_path = path
        self.data = self.load_config(path)

    def load_config(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"[에러] 설정 파일을 찾을 수 없습니다: {path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[에러] JSON 파싱 오류: {e}")
            return {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        """
        설정값을 변경하고 파일에 저장
        Args:
            key (str): 설정 키
            value: 설정 값
        Returns:
            bool: 저장 성공 여부
        """
        try:
            self.data[key] = value
            return self.save_config()
        except Exception as e:
            print(f"[에러] 설정 저장 중 오류 발생: {e}")
            return False

    def save_config(self):
        """
        현재 설정을 파일에 저장
        Returns:
            bool: 저장 성공 여부
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[에러] 설정 파일 저장 중 오류 발생: {e}")
            return False


def create_default_config():
    """기본 설정 파일 생성 예제"""
    config = Config()
    
    # 기본 설정값 정의
    default_settings = {
        "SLACK_WEBHOOK_URL": "",  # Slack 웹훅 URL
        "condition": "급등주",    # 선택된 조건식
        "budget_per_stock": 1000000,  # 종목당 투자금액
        "LOSS_CUTOFF": -5.0,     # 손절 기준
        "GAIN_CUTOFF": 5.0,      # 익절 기준
        "CHECK_INTERVAL": 10000,  # 점검 주기 (ms)
        "trading": {
            "enabled": True,      # 자동매매 활성화 여부
            "start_time": "09:00",
            "end_time": "15:30"
        }
    }
    
    # 설정 저장
    for key, value in default_settings.items():
        config.set(key, value)
    
    print("기본 설정 파일이 생성되었습니다.")
    return config


def example_usage():
    """Config 클래스 사용 예제"""
    # 설정 객체 생성
    config = Config()
    
    # 1. 설정값 읽기
    webhook_url = config.get("SLACK_WEBHOOK_URL", "")
    budget = config.get("budget_per_stock", 1000000)
    print(f"설정된 예산: {budget:,}원")
    
    # 2. 설정값 변경
    config.set("LOSS_CUTOFF", -6.0)
    config.set("GAIN_CUTOFF", 6.0)
    
    # 3. 복잡한 설정 구조
    trading_config = {
        "enabled": True,
        "start_time": "09:00",
        "end_time": "15:30"
    }
    config.set("trading", trading_config)
    
    # 4. 설정값 확인
    loss_cut = config.get("LOSS_CUTOFF")
    gain_cut = config.get("GAIN_CUTOFF")
    trading = config.get("trading", {})
    
    print("\n현재 설정값:")
    print(f"- 손절: {loss_cut}%")
    print(f"- 익절: {gain_cut}%")
    print(f"- 매매시간: {trading.get('start_time')} ~ {trading.get('end_time')}")


if __name__ == "__main__":
    print("Config 사용 예제 실행\n")
    
    # 1. 기본 설정 파일 생성
    print("1. 기본 설정 파일 생성")
    create_default_config()
    
    # 2. 설정 사용 예제
    print("\n2. 설정 사용 예제")
    example_usage()
    
    print("\n예제 실행이 완료되었습니다.")

