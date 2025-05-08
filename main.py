"""
Taiwan Stock Tick API 主程式
提供台灣股票市場 Tick 資料的 RESTful API 服務
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.endpoints.tick_data import router as tick_router
from app.api.endpoints.websocket import router as websocket_router
from app.core.config import settings
from app.core.logging_config import setup_logging

# 初始化日誌系統
logger = setup_logging()

# 創建 FastAPI 實例
app = FastAPI(
    title="Taiwan Stock Tick API",
    description="API for accessing Taiwan stock market tick data with enhanced formatting, price rounding, and real-time WebSocket streaming",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加 CORS 中間件以允許跨域請求
# 這對於允許不同域的前端應用訪問 API 是必要的
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 允許的來源列表，設置為 ["*"] 允許所有來源
    allow_credentials=True,               # 允許攜帶認證信息（cookies 等）
    allow_methods=["*"],                  # 允許的 HTTP 方法
    allow_headers=["*"],                  # 允許的 HTTP 頭部
)

# 包含 API 路由器
app.include_router(tick_router, prefix="/api/v1")

# 包含 WebSocket 路由器
app.include_router(websocket_router)

# 自定義 OpenAPI 架構
def custom_openapi():
    """
    自定義 OpenAPI 架構以提供更豐富的 API 文檔
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # 自定義文檔額外信息
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/", tags=["Root"])
async def root():
    """
    根端點，提供基本服務信息
    
    返回:
        dict: 包含服務名稱、版本、狀態和功能列表
    """
    return {
        "service": "Taiwan Stock Tick API (Enhanced)",
        "version": "1.1.0",
        "status": "running",
        "documentation": "/docs",
        "features": [
            "Tick data retrieval by date or date range",
            "Price rounding according to Taiwan Stock Exchange rules",
            "Date and time format conversion",
            "Real-time data subscription via WebSockets"
        ]
    }

if __name__ == "__main__":
    # 使用 uvicorn 啟動應用程序
    # 設置 host 為 0.0.0.0 以允許外部 IP 訪問
    uvicorn.run(
        "main:app",
        host=settings.HOST,          # 通常設為 "0.0.0.0" 以允許所有 IP 訪問
        port=settings.PORT,          # 通常設為 8000
        reload=settings.DEBUG,       # 開發模式下啟用熱重載
        log_level=settings.LOG_LEVEL.lower()  # 設置日誌級別
    )