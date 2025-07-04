import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
from PyQt5.QtCore import QTimer, Qt
from ui.main_ui import Ui_MainWindow
from kiwoom_api import KiwoomAPI
from config import Config
from log_manager import LogManager
from datetime import datetime
from PyQt5.QtGui import QBrush, QColor

class MainWindow(QMainWindow):
    logger = LogManager().get_logger()

    def __init__(self, app:QApplication):
        super().__init__()

        self.app = app

        self.CHECK_INTERVAL_MS = 10000   # 30초마다 잔고 조회
        self.LOSS_CUTOFF = -6.0          # 손절 기준 수익률(%)
        self.GAIN_CUTOFF = 6.0

        self.account_num = ''
        self.is_initial_condition_set = False  # 초기 조건식 설정 여부 플래그
        self.is_monitoring = False  # 조건식 모니터링 상태 플래그
        self.is_initial_account_set = False  # 초기 계좌 설정 여부 플래그
        self.is_logged_in = False  # 로그인 상태 플래그
        
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # UI 초기화
        self.init_ui()

        self.config = Config()
        # 예산 설정 (대소문자 모두 지원)
        self.buget_per_stock = self.config.get('BUDGET_PER_STOCK')
        if self.buget_per_stock is None:
            self.buget_per_stock = self.config.get('budget_per_stock')
        try:
            if self.buget_per_stock is not None:
                self.buget_per_stock = int(self.buget_per_stock)
        except Exception:
            self.buget_per_stock = None
            self.log("[설정오류] 주문 예산(budget_per_stock)이 올바르지 않습니다.")
        self.selected_condition = self.config.get('condition', '')  # 설정된 조건식 가져오기
        self.slack_webhook_url = self.config.get('SLACK_WEBHOOK_URL')
        self.LOSS_CUTOFF = self.config.get('LOSS_CUTOFF')
        self.GAIN_CUTOFF = self.config.get('GAIN_CUTOFF')
        self.saved_account = self.config.get('ACCOUNT_NUM', '')  # config에서 계좌번호 가져오기

        # Slack 알림 설정
        if self.slack_webhook_url:
            from slack_notifier import SlackNotifier
            self.slack = SlackNotifier(self.slack_webhook_url)
        else:
            self.slack = None
            self.logger.warning("Slack webhook URL이 설정되지 않았습니다. Slack 알림이 비활성화됩니다.")
                
        self.kiwoom = KiwoomAPI()
        self.kiwoom.login_event.connect(self.on_login_success)
        self.kiwoom.balance_event.connect(self.update_balance_table)  # 잔고 이벤트 연결
        
        # 버튼 이벤트 연결
        self.ui.pushButton_login.clicked.connect(self.toggle_login)
        self.ui.pushButton_load_conditions.clicked.connect(self.load_condition_list)
        self.ui.pushButton_start_condition.clicked.connect(self.toggle_condition_monitoring)

        # 조건식 이벤트 연결
        self.kiwoom.condition_list_event.connect(self.update_condition_combobox)
        self.kiwoom.condition_event.connect(self.on_condition_event)

        # 테스트 버튼
        #self.ui.pushButton_test_buy.clicked.connect(self.test_buy)
        #self.ui.pushButton_test_sell.clicked.connect(self.test_sell)

        # 계좌 선택 콤보 박스
        self.ui.comboBox_account.currentIndexChanged.connect(self.on_account_selected)

        # 조건식 선택 콤보박스 이벤트 연결
        self.ui.comboBox_condition.currentTextChanged.connect(self.on_condition_selected)

        # 손절/익절 설정값 변경 이벤트 연결
        self.ui.spinBox_loss_cut.valueChanged.connect(self.on_loss_cut_changed)
        self.ui.spinBox_gain_cut.valueChanged.connect(self.on_gain_cut_changed)

        # 사이드바 메뉴 선택 이벤트 연결
        self.ui.listWidget_menu.currentRowChanged.connect(self.on_menu_changed)

        # 테이블 초기화
        self.init_tables()

        self.account_list = []

        self.show()
        #self.showMaximized()

        # 자동 로그인 및 조건식 로드
        QTimer.singleShot(1000, self.auto_login)  # 1초 후 자동 로그인 시도

        # 조건식 저장 버튼 연결
        self.ui.pushButton_save_condition.clicked.connect(self.save_selected_condition)

        # 수동 매도 버튼 추가 및 연결
        self.ui.pushButton_manual_sell.clicked.connect(self.manual_sell_selected_stock)

        # 잔고 새로고침 버튼 연결
        self.ui.pushButton_refresh_balance.clicked.connect(self.refresh_balance_table)
    
    def init_ui(self):
        """UI 초기화"""
        # 첫 번째 메뉴 선택
        self.ui.listWidget_menu.setCurrentRow(0)
        
        # 손절/익절 초기값 설정
        self.ui.spinBox_loss_cut.setValue(abs(int(self.LOSS_CUTOFF)))
        self.ui.spinBox_gain_cut.setValue(int(self.GAIN_CUTOFF))

        # 테이블 크기 정책 설정
        self.ui.tableWidget_balance.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableWidget_balance.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tableWidget_balance.verticalHeader().setDefaultSectionSize(25)  # 행 높이 설정
        
        # 조건식 테이블 크기 정책 설정
        self.ui.tableWidget_condition_stocks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ui.tableWidget_condition_stocks.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ui.tableWidget_condition_stocks.verticalHeader().setDefaultSectionSize(25)  # 행 높이 설정

    def init_tables(self):
        """테이블 위젯 초기화"""
        # 잔고 테이블 설정
        self.ui.tableWidget_balance.setColumnCount(8)
        self.ui.tableWidget_balance.setHorizontalHeaderLabels(['', '종목코드', '종목명', '보유수량', '매입가', '현재가', '평가금액', '손익률'])
        
        # 조건식 종목 테이블 설정
        self.ui.tableWidget_condition_stocks.setColumnCount(6)
        self.ui.tableWidget_condition_stocks.setHorizontalHeaderLabels(['종목코드', '종목명', '현재가', '주문량', '상태', '시간'])

    def on_menu_changed(self, index):
        """
        사이드바 메뉴 선택 시 페이지 전환
        Args:
            index (int): 선택된 메뉴 인덱스
        """
        self.ui.stackedWidget_main.setCurrentIndex(index)
        
    def on_loss_cut_changed(self, value):
        """손절 기준 변경"""
        self.LOSS_CUTOFF = -abs(value)
        self.log(f"손절 기준 변경: {self.LOSS_CUTOFF}%")
        
    def on_gain_cut_changed(self, value):
        """익절 기준 변경"""
        self.GAIN_CUTOFF = value
        self.log(f"익절 기준 변경: {self.GAIN_CUTOFF}%")

    def log(self, message):
        """로그 출력"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{current_time}] {message}"
        self.ui.textEdit_log.append(log_message)
        self.logger.debug(message)

    def toggle_login(self):
        """로그인/로그아웃 토글"""
        if self.is_logged_in:
            self.logout()
        else:
            self.login()

    def login(self):
        self.kiwoom.comm_connect()

    def logout(self):
        """로그아웃: UI 및 상태 초기화 (OpenAPI는 실제 로그아웃 미지원)"""
        self.is_logged_in = False
        self.account_num = ''
        self.ui.comboBox_account.clear()
        self.ui.tableWidget_balance.setRowCount(0)
        self.ui.comboBox_condition.clear()
        self.ui.tableWidget_condition_stocks.setRowCount(0)
        self.ui.pushButton_login.setText("로그인")
        self.log("로그아웃 되었습니다.")

    def on_login_success(self, success):
        """로그인 성공 후 계좌 정보 가져오기"""
        if success:
            self.is_logged_in = True
            self.ui.pushButton_login.setText("로그아웃")
            accounts = self.kiwoom.get_account_list()
            
            self.log(f"계좌번호: {accounts}")
            self.ui.comboBox_account.clear()
            self.ui.comboBox_account.addItems(accounts)
            
            # config에 저장된 계좌번호가 있고 유효한 계좌번호인 경우 선택
            if self.saved_account and self.saved_account in accounts:
                self.ui.comboBox_account.setCurrentText(self.saved_account)
                self.account_num = self.saved_account
                self.log(f"저장된 계좌번호 '{self.saved_account}' 선택됨")
                QTimer.singleShot(1000, lambda: self.kiwoom.request_balance(self.account_num))
            # 저장된 계좌가 없거나 유효하지 않은 경우 첫 번째 계좌 선택
            elif accounts:
                self.account_num = accounts[0]
                self.ui.comboBox_account.setCurrentText(self.account_num)
                QTimer.singleShot(1000, lambda: self.kiwoom.request_balance(self.account_num))
            
            self.start_periodic_balance_check()

    def on_account_selected(self):
        """콤보박스에서 계좌 선택 시 호출"""
        selected_account = self.ui.comboBox_account.currentText()
        if not selected_account:
            self.logger.debug("계좌를 선택하세요.")
            return
        
        # 계좌번호가 변경된 경우에만 처리
        if selected_account != self.account_num:
            self.account_num = selected_account
            self.config.set('ACCOUNT_NUM', selected_account)  # config에 저장
            self.logger.debug(f"계좌번호 '{selected_account}' 저장됨")
            self.logger.debug(f"잔고 조회 요청: {selected_account}")
            self.kiwoom.request_balance(self.account_num)
        
    def update_balance_table(self, balance_data):
        """잔고 데이터를 테이블에 업데이트"""
        try:
            # 테이블 초기화
            self.ui.tableWidget_balance.setRowCount(0)
            
            if not balance_data:
                self.log("보유 종목이 없습니다.")
                return
            
            total_eval_amount = 0  # 총평가금액
            total_profit_loss = 0  # 총손익금액
            
            # 데이터 추가
            for row, item in enumerate(balance_data):
                self.ui.tableWidget_balance.insertRow(row)
                # 체크박스
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemIsUserCheckable)
                checkbox_item.setCheckState(Qt.Unchecked)
                self.ui.tableWidget_balance.setItem(row, 0, checkbox_item)
                # 종목코드
                code = item.get('종목코드', '')
                self.ui.tableWidget_balance.setItem(row, 1, QTableWidgetItem(code))
                # 종목명
                종목명 = item.get('종목명', '')
                self.ui.tableWidget_balance.setItem(row, 2, QTableWidgetItem(종목명))
                # 보유수량
                보유수량 = item.get('보유수량', '0').replace(',', '')
                self.ui.tableWidget_balance.setItem(row, 3, QTableWidgetItem(f"{int(보유수량):,}"))
                # 매입가
                매입가 = int(item.get('매입가', '0').replace(',', ''))
                self.ui.tableWidget_balance.setItem(row, 4, QTableWidgetItem(f"{매입가:,}"))
                # 현재가
                현재가_str = item.get('현재가', '0').replace(',', '')
                try:
                    현재가 = int(현재가_str)
                except Exception:
                    현재가 = 0
                if 현재가 == 0:
                    code_for_price = item.get('종목코드', '')
                    if code_for_price:
                        현재가 = self.kiwoom.get_current_price(code_for_price)
                self.ui.tableWidget_balance.setItem(row, 5, QTableWidgetItem(f"{현재가:,}"))
                # 평가금액
                평가금액 = int(item.get('평가금액', '0').replace(',', ''))
                self.ui.tableWidget_balance.setItem(row, 6, QTableWidgetItem(f"{평가금액:,}"))
                # 손익률
                손익률 = float(item.get('손익률', '0').replace('%', ''))
                손익률_item = QTableWidgetItem(f"{손익률:.2f}%")
                if 손익률 > 0:
                    손익률_item.setForeground(QBrush(QColor('red')))
                elif 손익률 < 0:
                    손익률_item.setForeground(QBrush(QColor('blue')))
                self.ui.tableWidget_balance.setItem(row, 7, 손익률_item)
                
                # 총계 계산
                total_eval_amount += 평가금액
                total_profit_loss += 평가금액 * (손익률 / 100)
            
            # 총계 행 추가
            total_row = self.ui.tableWidget_balance.rowCount()
            self.ui.tableWidget_balance.insertRow(total_row)
            
            # 총계 행 설정
            self.ui.tableWidget_balance.setItem(total_row, 0, QTableWidgetItem('총계'))
            self.ui.tableWidget_balance.setItem(total_row, 5, QTableWidgetItem(f"{total_eval_amount:,}"))
            
            # 총손익률 계산 및 설정
            if total_eval_amount > 0:
                total_profit_rate = (total_profit_loss / (total_eval_amount - total_profit_loss)) * 100
                total_profit_item = QTableWidgetItem(f"{total_profit_rate:.2f}%")
                
                if total_profit_rate > 0:
                    total_profit_item.setForeground(QBrush(QColor('red')))
                elif total_profit_rate < 0:
                    total_profit_item.setForeground(QBrush(QColor('blue')))
                
                self.ui.tableWidget_balance.setItem(total_row, 7, total_profit_item)
            
            # 총계 행 스타일 설정
            for col in range(self.ui.tableWidget_balance.columnCount()):
                item = self.ui.tableWidget_balance.item(total_row, col)
                if item:
                    item.setBackground(QBrush(QColor(240, 240, 240)))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
            
            self.update_orders_table()
        except Exception as e:
            self.log(f"잔고 업데이트 중 오류 발생: {str(e)}")

    # 조건식 리스트 불러오기
    def load_condition_list(self):
        self.kiwoom.get_condition_list()
        
    
    def test_buy(self):
        self.kiwoom.send_buy_order("8101216911", "084180", quantity=1, price=0, order_type="03")

    def test_sell(self):
        self.kiwoom.send_sell_order("8101216911", "084180", quantity=1, price=0, order_type="03")

    # 콤보박스 업데이트
    def update_condition_combobox(self, conditions):
        """조건식 콤보박스 업데이트"""
        self.ui.comboBox_condition.clear()
        self.ui.comboBox_condition.addItems(conditions)
        
        # Config에 저장된 조건식이 있으면 선택 (초기 설정)
        saved_condition = self.config.get('condition', '')
        if saved_condition and saved_condition in conditions and not self.is_initial_condition_set:
            self.is_initial_condition_set = True  # 초기 설정 완료 표시
            self.ui.comboBox_condition.setCurrentText(saved_condition)
            self.current_condition = saved_condition
            self.log(f"저장된 조건식 '{saved_condition}' 선택됨")
        
        self.log("조건식 리스트 불러오기 완료")

    # 조건식 감시 시작
    def start_condition_monitoring(self):
        """조건식 감시 시작"""
        condition_name = self.ui.comboBox_condition.currentText()
        if not condition_name:
            self.log("조건식을 선택해주세요.")
            return
            
        # 이미 모니터링 중인 경우 중복 시작 방지
        if self.is_monitoring and hasattr(self, 'current_condition') and self.current_condition == condition_name:
            self.log(f"이미 조건식 '{condition_name}'을 모니터링 중입니다.")
            return
            
        self.log(f"조건식 감시 시작: {condition_name}")
        self.kiwoom.start_condition_monitoring(condition_name)
        self.current_condition = condition_name  # 현재 모니터링 중인 조건식 저장
        self.is_monitoring = True
        
        # 시작 버튼 상태 업데이트
        self.ui.pushButton_start_condition.setText("모니터링 중지")

    #조건식 편입/이탈 이벤트 처리
    def on_condition_event(self, code, type_, cond_name):
        """조건식 편입/이탈 이벤트 처리"""
        event_type = "편입" if type_ == "I" else "이탈"
        self.log(f"[{cond_name}] {event_type} - 종목코드: {code}")

        if type_ == "I":
            try:
                # 중복 주문 방지
                if code in self.kiwoom.order_map:
                    order = self.kiwoom.order_map[code]
                    if order.get("filled", False):
                        self.log(f"[매수 스킵] 이미 체결된 종목 재편입: {code}")
                        return
                    else:
                        self.log(f"[매수 스킵] 이미 주문 중인 종목: {code}")
                        return

                selected_account = self.ui.comboBox_account.currentText()
                if not selected_account:
                    self.log("계좌가 선택되지 않았습니다. 매수 주문 생략.")
                    return

                # budget 체크
                if not hasattr(self, 'buget_per_stock') or self.buget_per_stock is None:
                    self.log("주문 예산이 설정되지 않았습니다.")
                    return
                
                budget = self.buget_per_stock
                if not isinstance(budget, (int, float)) or budget <= 0:
                    self.log(f"유효하지 않은 주문 예산: {budget}")
                    return

                delay_ms = 100  # 약간의 딜레이 후 주문

                def delayed_order():
                    try:
                        price = self.kiwoom.get_current_price(code)
                        if price <= 0:
                            self.log(f"[가격 조회 실패] 종목: {code}")
                            return

                        quantity = budget // price
                        if quantity < 1:
                            self.log(f"[예산 부족] {code} 현재가: {price:,}원, 예산: {budget:,}원 → 매수 불가")
                            return

                        # 매수 주문 실행
                        self.kiwoom.send_buy_order(
                            account=selected_account,
                            code=code,
                            quantity=quantity,
                            price=0,  # 시장가
                            order_type="03"  # 시장가
                        )

                        # 주문 정보를 테이블에 추가
                        self.update_condition_stock_table(code, "매수중", quantity)
                        self.log(f"[시장가 매수] {code} - 현재가: {price:,}원, 수량: {quantity}, 총액: {quantity * price:,}원")

                    except Exception as e:
                        self.log(f"[매수 주문 실패] {code} - 에러: {str(e)}")

                QTimer.singleShot(delay_ms, delayed_order)

            except Exception as e:
                self.log(f"[조건식 이벤트 처리 실패] {code} - 에러: {str(e)}")

    def update_condition_stock_table(self, code, status, quantity=0, price=0):
        """조건식 종목 테이블 업데이트"""
        try:
            # 현재 시간
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # 종목명과 현재가 조회
            stock_name = self.kiwoom.get_stock_name(code)
            current_price = self.kiwoom.get_current_price(code) if price == 0 else price
            
            # 기존 행이 있는지 확인
            found = False
            for row in range(self.ui.tableWidget_condition_stocks.rowCount()):
                if self.ui.tableWidget_condition_stocks.item(row, 0).text() == code:
                    found = True
                    # 상태 업데이트
                    self.ui.tableWidget_condition_stocks.item(row, 4).setText(status)
                    # 시간 업데이트
                    self.ui.tableWidget_condition_stocks.item(row, 5).setText(current_time)
                    break
            
            # 새로운 행 추가
            if not found:
                row = self.ui.tableWidget_condition_stocks.rowCount()
                self.ui.tableWidget_condition_stocks.insertRow(row)
                
                # 데이터 설정
                items = [
                    QTableWidgetItem(code),
                    QTableWidgetItem(stock_name),
                    QTableWidgetItem(f"{current_price:,}"),
                    QTableWidgetItem(f"{quantity:,}"),
                    QTableWidgetItem(status),
                    QTableWidgetItem(current_time)
                ]
                
                # 상태에 따른 색상 설정
                status_color = {
                    "매수중": QColor(255, 200, 200),  # 연한 빨강
                    "매수완료": QColor(255, 150, 150),  # 빨강
                    "매도중": QColor(200, 200, 255),  # 연한 파랑
                    "매도완료": QColor(150, 150, 255),  # 파랑
                    "실패": QColor(200, 200, 200)  # 회색
                }
                
                for col, item in enumerate(items):
                    if status in status_color and col == 4:  # 상태 컬럼
                        item.setBackground(QBrush(status_color[status]))
                    self.ui.tableWidget_condition_stocks.setItem(row, col, item)
            
        except Exception as e:
            self.log(f"테이블 업데이트 중 오류 발생: {str(e)}")

    def on_trade_event(self, event_type, code, quantity, price):
        """매매 체결 이벤트 처리"""
        try:
            if event_type == "매수체결":
                status = "매수완료"
                self.log(f"[매수체결] {code} - {quantity}주 @ {price:,}원")
            elif event_type == "매도체결":
                status = "매도완료"
                self.log(f"[매도체결] {code} - {quantity}주 @ {price:,}원")
            else:
                return
                
            self.update_condition_stock_table(code, status, quantity, price)
            
            # Slack 알림 전송
            if self.slack:
                try:
                    stock_name = self.kiwoom.get_stock_name(code)
                    trade_type = "매수" if event_type == "매수체결" else "매도"
                    
                    # 계좌번호 마스킹 처리 (뒤 4자리만 표시)
                    masked_account = f"...{self.account_num[-4:]}" if self.account_num else "계좌없음"
                    
                    message = (
                        f"{trade_type} 체결 알림 ({masked_account})\n"
                        f"• 종목: {stock_name} ({code})\n"
                        f"• 체결가: {price:,}원\n"
                        f"• 수량: {quantity:,}주\n"
                        f"• 총액: {price * quantity:,}원"
                    )
                    
                    color = "#36a64f" if trade_type == "매수" else "#ff4444"
                    self.slack.send_message(message, color)
                    
                except Exception as e:
                    self.log(f"Slack 알림 전송 실패: {str(e)}")
            
        except Exception as e:
            self.log(f"체결 처리 중 오류 발생: {str(e)}")

    def check_and_sell_losscut(self):
        def handle_balance(balance_list):
            for item in balance_list:
                try:
                    code = item["종목코드"]
                    qty = int(item["보유수량"].replace(",",""))
                    rate = float(item["손익률"].replace("%","").replace(",",""))
                except Exception as e:
                    self.log(f"원인: {e}")
                    continue
                
                if qty <=0 :
                    continue
                
                if rate <= self.LOSS_CUTOFF:
                    self.log(f"[손절 매도] {code} 손익률: {rate}%, 수량: {qty}")
                    self.kiwoom.send_sell_order(self.account_num, code, qty)
                
                if rate >= self.GAIN_CUTOFF:
                    self.log(f"[익절 매도] {code} 수익률: {rate}% → 시장가 매도")
                    self.kiwoom.send_sell_order(self.account_num, code, qty)                    
                
            
            # 한 번 연결 후 해제 (중복 연결 방지)
            self.kiwoom.balance_event.disconnect(handle_balance)

        self.kiwoom.balance_event.connect(handle_balance)
        self.kiwoom.request_balance(self.account_num)

    def start_periodic_balance_check(self):
        
        self.loss_timer = QTimer()
        self.loss_timer.timeout.connect(self.check_and_sell_losscut)
        self.loss_timer.start(self.CHECK_INTERVAL_MS)
        print("[자동 모니터링] 손실 종목 감시 시작")
    
    def on_condition_selected(self, condition_name):
        """조건식 선택 시 Config에 저장하고 모니터링 재시작"""
        if not condition_name:
            return
            
        # 초기 설정 중이면 저장하지 않고 리턴
        if not self.is_initial_condition_set:
            return
            
        # 이전 조건식과 동일하면 무시
        if hasattr(self, 'current_condition') and self.current_condition == condition_name:
            return
            
        # 이전 조건식 모니터링 중지
        if hasattr(self, 'current_condition') and self.current_condition:
            self.stop_condition_monitoring()
            
        # 새로운 조건식 저장 (사용자가 수동으로 선택한 경우에만)
        self.current_condition = condition_name
        self.config.set('condition', condition_name)
        self.log(f"조건식 '{condition_name}' 저장됨")
        
        QTimer.singleShot(1000, lambda: self.start_condition_monitoring())  # 1초 후 모니터링 시작

    def stop_condition_monitoring(self):
        """조건식 감시 중지"""
        if hasattr(self, 'current_condition') and self.current_condition:
            self.kiwoom.stop_condition_monitoring(self.current_condition)
            self.log(f"조건식 '{self.current_condition}' 모니터링 중지")
            self.current_condition = None
            self.is_monitoring = False
            
            # 시작 버튼 상태 업데이트
            self.ui.pushButton_start_condition.setText("모니터링 시작")

    def auto_login(self):
        """자동 로그인 및 조건식 로드"""
        self.login()
        # 로그인 후 2초 뒤에 조건식 로드
        QTimer.singleShot(5000, self.auto_condition_monitoring)
    
    def auto_condition_monitoring(self):
        """자동 조건식 감시 시작"""
        self.load_condition_list()
        
        # 2초 후에 저장된 조건식으로 감시 시작 시도
        QTimer.singleShot(2000, self.try_start_saved_condition)

    def try_start_saved_condition(self):
        """저장된 조건식으로 감시 시작 시도"""
        saved_condition = self.config.get('condition', '')
        if not saved_condition:
            self.log("저장된 조건식이 없습니다.")
            return
            
        current_conditions = [self.ui.comboBox_condition.itemText(i) 
                            for i in range(self.ui.comboBox_condition.count())]
        
        if saved_condition in current_conditions:
            self.ui.comboBox_condition.setCurrentText(saved_condition)
            self.log(f"저장된 조건식 '{saved_condition}' 선택")
            # 자동 시작 시에는 모니터링을 시작하지 않음
            self.start_condition_monitoring()
        else:
            self.log(f"저장된 조건식 '{saved_condition}'을 찾을 수 없습니다.")

    def toggle_condition_monitoring(self):
        """모니터링 시작/중지 토글"""
        if self.is_monitoring:
            self.stop_condition_monitoring()
        else:
            self.start_condition_monitoring()

    def save_selected_condition(self):
        """선택한 조건식을 config에 저장"""
        condition = self.ui.comboBox_condition.currentText()
        if condition:
            self.config.set('condition', condition)
            self.log(f"조건식 '{condition}'이(가) 저장되었습니다.")
        else:
            self.log("저장할 조건식을 선택하세요.")

    def manual_sell_selected_stock(self):
        """잔고 테이블에서 체크된 종목을 수동 매도"""
        sold_any = False
        for row in range(self.ui.tableWidget_balance.rowCount()):
            checkbox_item = self.ui.tableWidget_balance.item(row, 0)
            
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                code_item = self.ui.tableWidget_balance.item(row, 1)
                qty_item = self.ui.tableWidget_balance.item(row, 3)
                if not code_item or not qty_item:
                    self.log(f"[{row+1}행] 종목코드 또는 수량 정보를 찾을 수 없습니다.")
                    continue
                code = code_item.text()
                try:
                    qty = int(qty_item.text().replace(',', ''))
                except Exception:
                    self.log(f"[{row+1}행] 수량 정보가 올바르지 않습니다.")
                    continue
                if not code or qty <= 0:
                    self.log(f"[{row+1}행] 유효한 종목코드 또는 수량이 아닙니다.")
                    continue
                self.kiwoom.send_sell_order(self.account_num, code, qty)
                self.log(f"[수동 매도] {code} {qty}주 매도 주문 전송")
                sold_any = True
        if not sold_any:
            self.log("체크된 종목이 없습니다. 매도할 종목을 선택하세요.")
        self.update_orders_table()

    def refresh_balance_table(self):
        """잔고 테이블 새로고침"""
        if not self.account_num:
            self.log("계좌가 선택되지 않았습니다.")
            return
        self.kiwoom.request_balance(self.account_num)
        self.log("잔고 새로고침 요청 완료.")
        self.update_orders_table()

    def update_orders_table(self):
        """체결/미체결 주문내역 테이블 업데이트 (체결 완료는 제외)"""
        table = self.ui.tableWidget_orders
        table.setRowCount(0)
        for order in self.kiwoom.order_map.values():
            if order.get('filled', False):
                continue  # 체결 완료된 주문은 표시하지 않음
            row = table.rowCount()
            table.insertRow(row)
            order_id = order.get('order_id', order.get('code', ''))
            code = order.get('code', '')
            stock_name = self.kiwoom.get_stock_name(code) if code else ''
            qty = order.get('quantity', '')
            price = order.get('price', '')
            status = '미체결'
            order_type = '매도' if order.get('sell_sent', False) else '매수'
            time_str = order.get('time', '')
            items = [
                QTableWidgetItem(str(order_id)),
                QTableWidgetItem(str(code)),
                QTableWidgetItem(str(stock_name)),
                QTableWidgetItem(str(qty)),
                QTableWidgetItem(str(price)),
                QTableWidgetItem(status),
                QTableWidgetItem(order_type),
                QTableWidgetItem(time_str)
            ]
            for col, item in enumerate(items):
                table.setItem(row, col, item)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow(app=app)

    sys.exit(app.exec_())