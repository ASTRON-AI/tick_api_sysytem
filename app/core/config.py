"""
配置模塊 - 處理應用程序配置和環境變量
提供統一的配置管理界面
"""

import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 從 .env 文件加載環境變量
load_dotenv()

class Settings(BaseSettings):
    """
    應用程序設置類
    使用 pydantic 進行環境變量的類型驗證和轉換
    """
    # API 服務設置
    HOST: str = os.getenv("HOST", "0.0.0.0")  # 設置為 0.0.0.0 以允許所有 IP 訪問
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CORS_ORIGINS: List[str] = ["*"]  # 默認允許所有來源的跨域請求
    
    # 台灣股票 API 設置
    TW_STOCK_API_KEY: str = os.getenv("TW_STOCK_API_KEY", "pEbMu0tciRlqAYwNH71eKfOLvSZGjxry")
    TW_STOCK_API_HOST: str = os.getenv("TW_STOCK_API_HOST", "140.113.87.91")
    TW_STOCK_API_PORT: int = int(os.getenv("TW_STOCK_API_PORT", "3000"))
    TW_STOCK_DATA_ROOT: str = os.getenv("TW_STOCK_DATA_ROOT", "E:\\project\\tick raw data")
    
    # 格式轉換設置
    DEFAULT_CONVERT_FORMATS: bool = os.getenv("DEFAULT_CONVERT_FORMATS", "True").lower() == "true"
    
    # WebSocket 設置
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    
    @field_validator("CORS_ORIGINS")
    def parse_cors_origins(cls, v):
        """
        驗證並轉換 CORS_ORIGINS 設置
        支持字符串格式（逗號分隔）和列表格式
        
        參數:
            v: 輸入值
            
        返回:
            轉換後的列表
        """
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

# 創建全局設置實例
settings = Settings()