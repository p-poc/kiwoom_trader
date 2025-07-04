import sys
import time
import pandas as pd
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit
from PyQt5.QAxContainer import QAxWidget

class KiwoomAPI(QWidget):
    def __init__(self):
        super().__init__()

        # UI 파일 로드
        uic.loadUi("mainwindow.ui", self)


        # QAxWidget을 이용한 OpenAPI 객체 생성
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.kiwoom.OnEventConnect.connect(self.on_login)
        self.kiwoom.OnReceiveTrData.connect(self.on_receive_tr_data)
        self.kiwoom.OnReceiveConditionVer.connect(self.on_receive_condition_ver)
        self.kiwoom.OnReceiveTrCondition.connect(self.on_receive_tr_condition)

        # UI 요소 추가
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)

        self.login_button = QPushButton("키움증권 로그인", self)
        self.login_button.clicked.connect(self.comm_connect)

        self.balance_button = QPushButton("잔고 조회", self)
        self.balance_button.clicked.connect(self.request_balance)

        self.condition_button = QPushButton("조건식 검색", self)
        self.condition_button.clicked.connect(self.request_conditions)

        # UI 레이아웃 설정
        layout = QVBoxLayout()
        layout.addWidget(self.login_button)
        layout.addWidget(self.balance_button)
        layout.addWidget(self.condition_button)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

        self.account_num = ""  # 계좌번호 저장
        self.pass_num = "1225"

    def log(self, message):
        """로그 메시지 추가"""
        self.log_text.append(message)
        print(message)

    def comm_connect(self):
        """키움증권 OpenAPI 로그인 요청"""
        self.log("로그인 요청 중...")
        self.kiwoom.dynamicCall("CommConnect()")

    def on_login(self, err_code):
        """로그인 이벤트 핸들러"""
        if err_code == 0:
            self.log("로그인 성공!")
            self.account_num = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO").split(";")[0]
            self.log(f"계좌번호: {self.account_num}")
        else:
            self.log(f"로그인 실패 (에러 코드: {err_code})")

    def request_balance(self):
        """잔고 조회 요청"""
        if not self.account_num:
            self.log("로그인 후 다시 시도하세요.")
            return

        self.log("잔고 조회 요청 중...")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "계좌번호", self.account_num)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호", self.pass_num)
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.kiwoom.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        self.kiwoom.dynamicCall("CommRqData(QString, QString, int, QString)", "잔고조회", "opw00001", 0, "0101")

    def on_receive_tr_data(self, screen_no, rq_name, tr_code, record_name, prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트 핸들러"""
        if rq_name == "잔고조회":
            #self.log("잔고 데이터 수신 완료")
            print("잔고 데이터 수신 완료")
            item_count = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, record_name)
            balance_data = []

            for i in range(item_count):
                item = {
                    "종목명": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "종목명").strip(),
                    "보유수량": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "보유수량").strip(),
                    "매입가": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "매입가").strip(),
                    "평가금액": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "평가금액").strip(),
                    "손익률": self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, i, "손익률").strip(),
                }
                balance_data.append(item)

            df = pd.DataFrame(balance_data)

            print(df)
            

            
            
            #self.log(f"\n{df.to_string(index=False)}")

    def request_conditions(self):
        """조건식 리스트 요청"""
        self.log("조건식 리스트 요청 중...")
        self.kiwoom.dynamicCall("GetConditionLoad()")

    def on_receive_condition_ver(self, ret, msg):
        """조건식 리스트 수신 이벤트"""
        if ret == 1:
            self.log("조건식 리스트 수신 성공")
            conditions = self.kiwoom.dynamicCall("GetConditionNameList()")
            self.log(f"조건식 리스트: {conditions}")

            if conditions:
                first_condition = conditions.split(";")[0]
                condition_index, condition_name = first_condition.split("^")

                self.log(f"조건식 적용: {condition_name}")
                self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)", "0101", condition_name, int(condition_index), 1)

    def on_receive_tr_condition(self, screen_no, codes, condition_name, condition_index, inquiry):
        """조건 검색 결과 수신 이벤트"""
        self.log(f"조건식 '{condition_name}' 검색 결과 수신")
        if codes:
            stock_list = codes.split(";")
            self.log(f"검색된 종목 코드: {', '.join(stock_list)}")
        else:
            self.log("조건 검색 결과 없음.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KiwoomAPI()
    window.show()
    sys.exit(app.exec_())