import logging
import os
from datetime import datetime

class LogManager:
    _instance = None
    _logger = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_name="trading", log_dir="logs", level=logging.DEBUG):
        if hasattr(self, '_initialized') and self._initialized:
            return

        if LogManager._logger is None:
            logger = logging.getLogger(log_name)
            logger.setLevel(level)

            if logger.hasHandlers():
                logger.handlers.clear()


            base_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)

            today = datetime.now().strftime("%Y-%m-%d")
            log_file = os.path.join(log_dir, f"{log_name}_{today}.log")

            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S')

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            LogManager._logger = logger

        self._initialized = True

    # def _setup_handlers(self, log_name, log_dir, level):
    #     # 로그 디렉토리 생성
    #     os.makedirs(log_dir, exist_ok=True)

    #     # 날짜 기반 파일명
    #     today = datetime.now().strftime("%Y-%m-%d")
    #     log_file = os.path.join(log_dir, f"{log_name}_{today}.log")

    #     # 로그 포맷
    #     formatter = logging.Formatter(
    #         '[%(asctime)s] [%(levelname)s] %(message)s',
    #         datefmt='%Y-%m-%d %H:%M:%S'
    #     )

    #     # 파일 핸들러
    #     file_handler = logging.FileHandler(log_file, encoding='utf-8')
    #     file_handler.setLevel(level)
    #     file_handler.setFormatter(formatter)
    #     self.logger.addHandler(file_handler)

    #     # 콘솔 핸들러
    #     console_handler = logging.StreamHandler()
    #     console_handler.setLevel(level)
    #     console_handler.setFormatter(formatter)
    #     self.logger.addHandler(console_handler)

    def get_logger(self):
        return LogManager._logger