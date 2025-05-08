"""
WebSocket API 端點模塊
提供 Taiwan Stock Tick API 的實時數據流功能
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, List, Optional, Any
import logging
import pandas as pd
import numpy as np
import json
from datetime import datetime, date
import asyncio
import time

from app.services.tick_api import TWStockTickService
from app.api.endpoints.tick_data import get_tick_service, convert_decimal, custom_process_price_columns, custom_process_volume_columns
from app.services.utils.date_time_utils import format_date_to_yyyymmdd
from app.core.config import settings

# 創建 API 路由器
router = APIRouter(
    tags=["WebSocket"]
)

# 取得 logger 實例
logger = logging.getLogger("tw_stock_api")

# 存儲所有活躍的WebSocket連接
active_connections: Dict[str, List[WebSocket]] = {}


@router.websocket("/ws/tick/{stock_id}/{date}")
async def websocket_tick_data(
    websocket: WebSocket, 
    stock_id: str, 
    date: str,
    tick_service: TWStockTickService = Depends(get_tick_service)
):
    """
    WebSocket端點，用於訂閱特定股票和日期的Tick數據流
    
    參數:
        websocket: WebSocket連接
        stock_id: 股票代碼
        date: 日期 (YYYYMMDD, YYYY-MM-DD, 或 YYYY/MM/DD 格式)
        tick_service: TWStockTickService實例
    """
    await websocket.accept()
    
    # 生成唯一的連接ID
    connection_id = f"{stock_id}_{date}"
    
    # 將連接添加到活躍連接列表
    if connection_id not in active_connections:
        active_connections[connection_id] = []
    active_connections[connection_id].append(websocket)
    
    try:
        # 使用修正後的方法獲取 tick 數據
        data = await tick_service.get_ws_tick_data(
            stock_id=stock_id,
            date=date,
            convert_formats=True
        )
        
        if not data:
            await websocket.send_json({"error": f"無法獲取股票 {stock_id} 在 {date} 的數據"})
            await websocket.close()
            return
        
        total_records = len(data)
        logger.info(f"開始為股票 {stock_id} 在 {date} 的WebSocket流，總記錄數: {total_records}")
        
        # 發送總記錄數信息
        await websocket.send_json({
            "type": "info", 
            "message": f"開始數據流，總記錄數: {total_records}", 
            "total_records": total_records
        })
        
        # 每1毫秒發送一行數據
        start_time = time.time()
        for i, row in enumerate(data):
            try:
                # 添加進度信息
                if (i + 1) % 1000 == 0 or i == total_records - 1:
                    progress = (i + 1) / total_records * 100
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(f"已發送 {i+1}/{total_records} 條記錄 ({progress:.2f}%), 速率: {rate:.2f} 條/秒")
                
                # 添加元數據
                row["_meta"] = {
                    "record_number": i + 1,
                    "total_records": total_records,
                    "progress": progress if 'progress' in locals() else (i + 1) / total_records * 100
                }
                
                await websocket.send_json(row)
                await asyncio.sleep(0.001)  # 等待1毫秒
                
            except WebSocketDisconnect:
                logger.info(f"客戶端斷開連接，股票: {stock_id}，日期: {date}，進度: {i+1}/{total_records}")
                break
            except Exception as e:
                logger.error(f"發送數據時出錯: {str(e)}")
                await websocket.send_json({"error": f"發送數據時出錯: {str(e)}"})
                break
        
        # 數據發送完畢
        elapsed = time.time() - start_time
        rate = total_records / elapsed if elapsed > 0 else 0
        logger.info(f"完成WebSocket流，股票: {stock_id}，日期: {date}，總記錄數: {total_records}，用時: {elapsed:.2f}秒，速率: {rate:.2f} 條/秒")
        
        await websocket.send_json({
            "type": "completed", 
            "message": "所有 tick 數據已發送完畢",
            "stats": {
                "total_records": total_records,
                "elapsed_seconds": elapsed,
                "records_per_second": rate
            }
        })
    
    except Exception as e:
        logger.error(f"WebSocket連接錯誤: {str(e)}")
        await websocket.send_json({"error": str(e)})
    
    finally:
        # 清理連接
        if connection_id in active_connections:
            active_connections[connection_id].remove(websocket)
            if not active_connections[connection_id]:
                del active_connections[connection_id]
        await websocket.close()
        
@router.websocket("/ws/heartbeat")
async def websocket_heartbeat(websocket: WebSocket):
    """
    WebSocket心跳端點，用於保持連接活躍
    
    參數:
        websocket: WebSocket連接
    """
    await websocket.accept()
    
    try:
        while True:
            # 發送心跳訊息
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            })
            
            # 等待下一個心跳間隔
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
    
    except WebSocketDisconnect:
        logger.debug("心跳連接已斷開")
    except Exception as e:
        logger.error(f"心跳連接錯誤: {str(e)}")
    finally:
        await websocket.close()