# from PyQt5.QtWidgets import QApplication
# import sys
# import pythoncom
# import win32com.client
# import platform

# class Kiwoom:
#     def __init__(self):
#         pythoncom.CoInitialize()
#         self.api = win32com.client.Dispatch("KHOPENAPI.KHOpenAPICtrl.1")
#         print("키움 OpenAPI 객체 생성 완료")

#     def login(self):
#         self.api.CommConnect()


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     kiwoom = Kiwoom()
#     kiwoom.login()
#     app.exec_()  # 이벤트 루프 실행

import sys
from PyQt5.QAxContainer import *
from PyQt5.QtWidgets import *
import pythoncom

login = False
def OnEventConnect(code):
    global login 
    login = True
    print("login is done", code)

app = QApplication(sys.argv)
ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
ocx.OnEventConnect.connect(OnEventConnect) # 시그널 슬롯 연결 설정

ocx.dynamicCall("CommConnect()") # 로그인 메서드 호출

# 로그인이 완료될 때까지 이벤트를 처리하면서 대기
while login is False:
    pythoncom.PumpWaitingMessages()