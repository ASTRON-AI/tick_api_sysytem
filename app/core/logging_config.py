"""
日誌配置模塊 - 設置應用程序的日誌記錄系統
提供統一的日誌配置和格式
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

def setup_logging():
    """
    配置應用程序的日誌系統
    
    創建控制台和文件處理器，設置格式和級別
    
    返回:
        logging.Logger: 配置好的日誌記錄器
    """
    # 創建 logs 目錄（若不存在）
    os.makedirs("logs", exist_ok=True)
    
    # 創建 logger
    logger = logging.getLogger("tw_stock_api")
    logger.setLevel(logging.INFO)
    
    # 清除現有的 handlers（如果有）
    if logger.handlers:
        logger.handlers.clear()
    
    # 創建格式化器
    # 文件日誌使用詳細格式
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # 控制台日誌使用簡潔格式
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 創建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # 創建文件 handler（用於寫入循環日誌）
    current_date = datetime.now().strftime("%Y-%m-%d")
    file_handler = RotatingFileHandler(
        f"logs/tw_stock_api_{current_date}.log",
        maxBytes=10485760,  # 10MB
        backupCount=10  # 保留 10 個備份文件
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # 添加 handlers 到 logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # 設置 propagate 為 False（如果這是根 logger）
    # 這確保日誌消息不會被傳播到父級 logger
    logger.propagate = False
    
    logger.info("日誌系統已初始化")
    return logger