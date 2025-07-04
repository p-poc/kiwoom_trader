import sqlite3
from datetime import datetime

class TradeLogger_Sqlite3:
    def __init__(self, db_path='trade_log.db'):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
    
    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            code TEXT,
            trade_type TEXT,
            quantity INTEGER,
            price INTEGER,
            total_amount INTEGER
        )
        """
        self.conn.execute(query)
        self.conn.commit()
    
    def log_trade(self, code, trade_type, quantity, price):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total = quantity * price

        query = """
        INSERT INTO trades (timestamp, code, trade_type, quantity, price, total_amount)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        self.conn.execute(query, (now, code, trade_type, quantity, price, total))
        self.conn.commit()

        print(f"[DB 저장] {trade_type} - {code} {quantity}주 @ {price} → {total}원")