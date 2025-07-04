import pandas as pd
from datetime import datetime

from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import pyqtSignal, QObject, QTimer
from trade_logger import TradeLogger_Sqlite3
from log_manager import LogManager

class KiwoomAPI(QObject):
    login_event = pyqtSignal(bool)  # 로그인 완료 시그널
    balance_event = pyqtSignal(list)  # 잔고 조회 완료 시그널
    condition_event = pyqtSignal(str, str, str)  # 실시간 조건식 결과 이벤트 (종목코드, 이벤트종류, 조건이름)
    condition_list_event = pyqtSignal(list)

    logger = LogManager().get_logger()

    def __init__(self):
        super().__init__()
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        self.account_num = ""
        self.order_map = {} # 주문 번호 -> 주문 정보
        self.active_conditions = {}  # 실행 중인 조건식 상태 추적
        self.screen_number = 5000  # 화면번호 기본값

        self.kiwoom.OnEventConnect.connect(self.on_login)
        self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr_data)
        self.kiwoom.OnReceiveConditionVer.connect(self.on_receive_condition_ver)
        self.kiwoom.OnReceiveRealCondition.connect(self.on_receive_real_condition)
        self.kiwoom.OnReceiveChejanData.connect(self.on_receive_chejan_data)

        self.conditions = []  # 조건식 리스트 저장용

        self.db = TradeLogger_Sqlite3(db_path="trade_log.db")
        self.db.create_table()


    def get_instance(self):
        return self.kiwoom
    
    def comm_connect(self):
        """키움증권 OpenAPI 로그인 요청"""
        self.logger.debug("로그인 요청 중...")
        self.kiwoom.dynamicCall("CommConnect()")

    def on_login(self, err_code):
        """로그인 이벤트 핸들러"""
        if err_code == 0:
            self.logger.debug("로그인 성공!")
            self.login_event.emit(True)  # UI에 로그인 성공 신호 보냄
        else:
            self.logger.debug(f"로그인 실패 (에러 코드: {err_code})")
            self.login_event.emit(False)        
    
    def get_account_list(self):
        """계좌 목록 조회"""
        accounts = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        return accounts.strip().split(";")[:-1]
    
    # def get_stock_code_by_name(self, name):
    #     """
    #     종목명으로 종목코드를 조회하는 함수
    #     예: "삼성전자" → "005930"
    #     """
    #     code = self.kiwoom.dynamicCall("GetCodeByName(QString)", name).strip()
    #     if not code:
    #         print(f"[경고] 종목명을 코드로 변환 실패: {name}")
    #     return code
    

    def request_balance(self, account_number, password="0000"):
        """잔고 조회 요청"""
        #self.logger.debug("잔고 조회 요청")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_number)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", password)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        #self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "잔고조회", "opw00004", 0, "2000")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "계좌평가잔고내역조회", "opw00018", 0, "2000")

    def on_receive_tr_data(self, screen_no, rq_name, tr_code, record_name, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트 핸들러"""
        if rq_name == "계좌평가잔고내역조회":
            #self.logger.debug("잔고 조회 수신")
            item_count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, record_name)
            balance_data = []

            #self.logger.debug("\n[계좌 요약 정보]")
            total_asset = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, 0, "총자산평가금액").strip()
            total_profit = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, 0, "총평가손익금액").strip()
            total_rate = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, 0, "총수익률(%)").strip()            

            for i in range(item_count):
                code = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)",tr_code, record_name, i, "종목번호").strip()
                if code.startswith("A"):
                    code = code[1:]

                item = {
                    "종목코드": code,    
                    "종목명": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "종목명").strip(),
                    "보유수량": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "보유수량").strip(),
                    "매입가": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "매입가").strip(),
                    "평가금액": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "평가금액").strip(),
                    "손익률": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "수익률(%)").strip(),
                }
                balance_data.append(item)

            self.update_order_map_from_balance(balance_data)
            self.balance_event.emit(balance_data)  # UI에 잔고 데이터 전달
    
    def get_condition_list(self):
        # 조건식 리스트 요청
        self.kiwoom.dynamicCall("GetConditionLoad()")

    def on_receive_condition_ver(self, ret, msg):
        """
        조건식 리스트 수신 이벤트
        ret: 성공 여부 (1 = 성공)
        msg: 메시지
        """
        if ret == 1:
            data = self.kiwoom.dynamicCall("GetConditionNameList()")
            self.logger.debug("조건식 리스트:")
            self.conditions.clear()
            condition_items = []
            for cond in data.split(';'):
                if cond:
                    cond_id, cond_name = cond.split('^')
                    self.conditions.append((int(cond_id), cond_name))
                    condition_items.append(cond_name)
                    print(f"   ID: {cond_id}, 이름: {cond_name}")
            
            # UI에 전달
            self.condition_list_event.emit(condition_items)
            
        else:
            self.logger.debug("조건식 불러오기 실패")
    
    def start_condition_monitoring(self, cond_name: str):
        """조건식을 실행하여 실시간 감시 시작"""
        cond_id = None
        for cid, name in self.conditions:
            if name == cond_name:
                cond_id = cid
                break
        
        if cond_id is None:
            self.logger.error(f"조건식 '{cond_name}'을 찾을 수 없습니다.")
            return
        
        screen_no = "5000" # 화면 번호는 임의로 지정 ( 충돌 피할 것 )
        search = 1 # 검색 후 실시간 감시
        #realtime = 1
        self.logger.debug(f"조건식 감시 시작 : {cond_name} (ID: {cond_id})")

        self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)", screen_no, cond_name, cond_id, search)

    def stop_condition_monitoring(self, cond_name: str):
        """조건식 실시간 감시 중지"""
        cond_id = None
        for cid, name in self.conditions:
            if name == cond_name:
                cond_id = cid
                break
        
        if cond_id is None:
            self.logger.error(f"조건식 '{cond_name}'을 찾을 수 없습니다.")
            return
        
        screen_no = "5000"  # start_condition_monitoring과 동일한 화면번호 사용
        
        # SendConditionStop 함수 호출하여 감시 중지
        self.kiwoom.dynamicCall("SendConditionStop(QString, QString, int)", screen_no, cond_name, cond_id)
        self.logger.debug(f"조건식 감시 중지 : {cond_name} (ID: {cond_id})")

    def on_receive_real_condition(self, code, type_, cond_name, cond_index):
        """
        조건식에 해당되는 종목 실시간 수신
        - code : 종목 코드
        - type : "I"(편입), "D"(이탈)
        - cond_name: 조건식 이름
        """
        self.logger.debug(f"[조건검색 실시간] 종목코드: {code}, 이벤트: {type_}, 조건명: {cond_name}")
        self.condition_event.emit(code, type_, cond_name)

    def send_buy_order(self, account, code, quantity, price=0, order_type="03", retry_count=0):
        """
        매수 주문 실행
        - code: 종목코드 (ex: A005930)
        - quantity: 매수 수량
        - price: 주문 가격
        - 주문 유형 (1: 매수, 2: 매도도)
        - order_type: 주문 유형 (03: 시장가, 00: 지정가, 05: 조건부 지정가: 10:최유리)
        """
        sceen_no = "6000"

        order_id = self.kiwoom.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            ["자동매수", sceen_no, account, 1, code, quantity, price, order_type, ""]
        )

        self.logger.debug(f"[주문 전송] 종목: {code}, 주문수량: {quantity}, 주문가격: {price}, 계좌 : {account}, 주문 타입 : {order_type}")

        # 주문번호 저장 (order_id는 실제 반환 안되므로 별도 추적 필요)
        self.order_map[code] = {
            "account": account,
            "code": code,
            "quantity": quantity,
            "price": price,
            "retry": retry_count,
            "filled": False,
            "sell_sent": False
        }

        # # 5초 후 체결 여부 확인 및 재시도
        # QTimer.singleShot(5000, lambda: self.check_order_fill(code))


        # if price is None:
        #     price = self.get_current_price(code)
        
        # if price == 0:
        #     print(f"[매수 실패] {code} 현재가 조회 실패")
        #     return

        # self.kiwoom.dynamicCall(
        #     "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
        #     ["자동매수", sceen_no, account, 1, code, quantity, price, "", ""]
        # )
        # print(f"[자동매수] 계좌: {account}, 종목: {code}, 수량: {quantity}, 가격: {price}")
    
    def send_buy_order_by_budget(self, account, code, budget, order_type="03"):
        """
        예산 기반 지정가 매수 주문
        - budget: 매수 금액 (예: 100000 -> 10만원)
        - order_type: 주문 유형 (2: 지정가)
        """
        price = self.get_current_price(code)
        if price == 0:
            self.logger.error(f"[매수 실패] {code} 현재가 조회 실패")
            return
        
        quantity = budget // price  # 소수점 버리고 정수 몫만 반환
        if quantity < 1:
            self.logger.error(f"[매수 실패] 예산 {budget}으로 매수 가능한 수량이 없습니다. 현재가: {price}")
            return
        
        self.send_buy_order(account, code, quantity, price, order_type)
    
    def on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        #gubun : "0" : 체결, "1": 미체결/접수/확인
        
        if gubun != "0": # 주문체결이 아닌 경우 무시
            return
        
        code = self.kiwoom.dynamicCall("GetChejanData(int)", 9001).strip() # 종목코드
        if code.startswith("A"):
            code = code[1:]
        
        filled_qty = self.kiwoom.dynamicCall("GetChejanData(int)", 911).strip() #체결수량
        trade_type = self.kiwoom.dynamicCall("GetChejanData(int)", 905).strip() # "매수" 또는 "매도"
        price = self.kiwoom.dynamicCall("GetChejanData(int)", 910).strip()      # 체결가
        
        self.logger.debug(f"gubun: {gubun}, code: {code}, filled_qty: {filled_qty}, price: {price}, trade_type: {trade_type}")
        
        if not filled_qty or int(filled_qty) <= 0:
            return
        
        if code not in self.order_map:
            self.logger.debug(f"[체결 무시] order_map에 없음: {code}")
            return

        if trade_type == "+매수":
            self.order_map[code]["filled"] = True
            self.logger.debug(f"[매수 체결 완료] {code}, 수량: {filled_qty}, 가격: {price}")
        
        elif trade_type == "-매도":
            self.logger.debug(f"[매도 체결 완료] {code}, 수량: {filled_qty}, 가격: {price}")
        
        
        # if code in self.order_map and filled_qty and int(filled_qty) > 0:
        #     self.order_map[code]["filled"] = True
        #     print(f"[체결 완료] {code}, 체결 수량: {filled_qty}")

        #     # 자동 매도 실행 (익절/손절 설정 예시)
        #     # if not self.order_map[code]["sell_sent"]:
        #     #     self.order_map[code]["sell_sent"] = True
        #     #     QTimer.singleShot(2000, lambda: self.send_sell_order(code))
        # else:
        #     print(f"code: {code}, order: {self.order_map}, fill_qty: {filled_qty}")
    
    def check_order_fill(self, code):
        order = self.order_map.get(code)
        self.logger.debug(f"order 값 : {order}")

        if not order:
            return
        
        # if not order["filled"]:
        #     if order["retry"] < 2:
        #         print(f"[미체결] {code}, 재시도 {order['retry'] + 1)}회")
        #         # 재주문
        #         self.send_buy_order(
        #             order["account"],
        #             order["code"],
        #             order["quantity"],
        #             order["price"],
        #             order_type=2,
        #             retry_count=order["retry"] + 1
        #         )
        #     else:
        #         print(f"[재시도 종료] {code} 최대 재시도 횟수 도달")

        # if order["retry"] < 1:
        #     print(f"[미체결] {code}, 시장가로 재주문 시도")
        #     self.send_buy_order(
        #         order["account"],
        #         code,
        #         order["quantity"],
        #         price=0, # 시장가
        #         order_type=1,
        #         retry_count=order["retry"] + 1
        #     )
        # else:
        #     print(f"[매수 실패] {code} 최대 재시도 도달")


    # 시장가 매도시 target_price = 0, order_type="03"
    def send_sell_order(self, account, code, quantity, price=0, order_type="03", retry_count=0):
        order = self.order_map.get(code)
        if not order:
            return
        
        #account = order["account"]
        #quantity = order["quantity"]
        #entry_price = order["price"]

        # 익절 2% 위, 손절 2% 아래
        #target_price = int(entry_price * 1.02)
        #stop_loss_price = int(entry_price * 0.98)

        if order_type == "03":
            price = 0
            self.logger.debug(f"[자동매도, 시장가] {code} 수량: {quantity}, 매도가: {price}")
        else:
            self.logger.debug(f"[자동매도, 지정가] {code} 수량: {quantity}, 매도가: {price}")
        
        screen_no = "7000"
        #사용자 정의 요청명, 화면번호, 계좌번호, 주문유형코드(1매수,2매도), 종목코드, 주문수량, 주문가격(시장가0), 호가구분(시장가"03", 지정가"00"), 원주문번호
        self.kiwoom.dynamicCall(
               "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                ["자동매도", screen_no, account, 2, code, quantity, price, order_type, ""]
        )
    
    def get_current_price(self, code):
        """
        종목코드의 현재가 조회 (호가 기준 가격)
        """
        price = self.kiwoom.dynamicCall("GetMasterLastPrice(QString)", code)
        try:
            return int(price)
        except ValueError:
            return 0
    
    def update_order_map_from_balance(self, balance_data):
        """
        잔고 데이터를 기반으로 order_map을 갱신
        """
        for item in balance_data:
            name = item["종목명"]
            code = item["종목코드"]

            quantity = int(item["보유수량"].replace(",", ""))
            # 수정 필요. 매입가가 안올라오는 문제 있음.
            try:
                price = int(item["매입가"].replace(",", ""))
            except:
                price = 0

            if quantity > 0:
                self.order_map[code] = {
                    "account": self.account_num,
                    "code": code,
                    "quantity": quantity,
                    "price": price,
                    "retry": 0,
                    "filled": True,       # 이미 체결된 상태
                    "sell_sent": False    # 아직 매도 안한 상태
                }
                #self.logger.debug(f"[보유종목 등록] {code} 수량: {quantity}, 매입가: {price}")
    
    def get_stock_name(self, code):
        """종목코드로 종목명 조회"""
        return self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code).strip()
    
