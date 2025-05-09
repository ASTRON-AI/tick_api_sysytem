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
from datetime import datetime, date, timedelta
import asyncio
import time

from app.services.tick_api import TWStockTickService
from app.api.endpoints.tick_data import get_tick_service, convert_decimal, custom_process_price_columns, custom_process_volume_columns
from app.services.utils.date_time_utils import format_date_to_yyyymmdd, format_display_time
from app.core.config import settings

# 創建 API 路由器
router = APIRouter(
    tags=["WebSocket"]
)

# 取得 logger 實例
logger = logging.getLogger("tw_stock_api")

# 存儲所有活躍的WebSocket連接
active_connections: Dict[str, List[WebSocket]] = {}


def calculate_trade_volume(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    計算每筆成交的單次成交量
    根據累積成交量(acc_transaction_volume)計算每筆match_flag="Y"的單次成交量(trade_volume)
    
    參數:
        data: 股票Tick資料列表
        
    返回:
        處理後的股票Tick資料列表，包含單次成交量trade_volume欄位
    """
    if not data:
        return data
    
    # 創建一份資料的複本，避免修改原始資料
    result = data.copy()
    
    # 追蹤上一次成交的累積成交量
    last_acc_volume = 0
    
    for i, row in enumerate(result):
        # 檢查是否為成交記錄
        is_match = row.get('match_flag') == 'Y'
        
        # 獲取當前累積成交量
        current_acc_volume = row.get('acc_transaction_volume')
        
        # 如果是成交記錄且累積成交量存在
        if is_match and current_acc_volume is not None:
            # 計算單次成交量
            if i == 0 or last_acc_volume == 0:
                # 如果是第一筆記錄或前面沒有成交，使用當前累積成交量作為單次成交量
                row['trade_volume'] = current_acc_volume
            else:
                # 計算增量成交量
                row['trade_volume'] = current_acc_volume - last_acc_volume
            
            # 更新上一次成交量
            last_acc_volume = current_acc_volume
        else:
            # 非成交記錄，設置單次成交量為0或null
            row['trade_volume'] = 0
    
    return result


@router.websocket("/ws/tick/{stock_id}/{date}")
async def websocket_tick_data(
    websocket: WebSocket, 
    stock_id: str, 
    date: str,
    tick_service: TWStockTickService = Depends(get_tick_service),
    scale_factor: float = 1.0,  # 時間比例因子，可以加快或減慢模擬速度
    calculate_volumes: bool = True  # 是否計算單次成交量
):
    """
    WebSocket端點，用於訂閱特定股票和日期的Tick數據流
    
    參數:
        websocket: WebSocket連接
        stock_id: 股票代碼
        date: 日期 (YYYYMMDD, YYYY-MM-DD, 或 YYYY/MM/DD 格式)
        tick_service: TWStockTickService實例
        scale_factor: 時間比例因子 (1.0為實時，小於1.0加快，大於1.0減慢)
        calculate_volumes: 是否計算單次成交量 (預設為True)
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
        
        # 計算單次成交量
        if calculate_volumes:
            data = calculate_trade_volume(data)
        
        total_records = len(data)
        logger.info(f"開始為股票 {stock_id} 在 {date} 的WebSocket流，總記錄數: {total_records}")
        
        # 發送總記錄數信息
        await websocket.send_json({
            "type": "info", 
            "message": f"開始數據流，總記錄數: {total_records}", 
            "total_records": total_records,
            "features": ["單次成交量計算"] if calculate_volumes else []
        })
        
        # 使用 display_time 作為傳送間隔的基準
        start_time = time.time()
        last_time = None
        
        for i, row in enumerate(data):
            try:
                current_time = row.get('display_time')
                
                # 處理時間間隔
                if i > 0 and current_time and last_time:
                    # 解析時間字符串為時間對象
                    try:
                        # 檢查 display_time 格式
                        if isinstance(current_time, str):
                            if ':' in current_time:  # 格式如 "09:00:01.500"
                                current_time_obj = datetime.strptime(current_time, "%H:%M:%S.%f" if '.' in current_time else "%H:%M:%S")
                                last_time_obj = datetime.strptime(last_time, "%H:%M:%S.%f" if '.' in last_time else "%H:%M:%S")
                            else:  # 格式如 "090001500"
                                # 提取時、分、秒和毫秒（如果有）
                                hours = int(current_time[:2])
                                minutes = int(current_time[2:4])
                                seconds = int(current_time[4:6])
                                microseconds = int(current_time[6:]) * 1000 if len(current_time) > 6 else 0
                                
                                current_time_obj = datetime(1900, 1, 1, hours, minutes, seconds, microseconds)
                                
                                hours = int(last_time[:2])
                                minutes = int(last_time[2:4])
                                seconds = int(last_time[4:6])
                                microseconds = int(last_time[6:]) * 1000 if len(last_time) > 6 else 0
                                
                                last_time_obj = datetime(1900, 1, 1, hours, minutes, seconds, microseconds)
                        else:
                            # 如果不是字符串，跳過時間間隔計算
                            raise ValueError("display_time format not recognized")
                            
                        # 計算兩個時間點之間的差異（秒）
                        time_diff = (current_time_obj - last_time_obj).total_seconds()
                        
                        # 應用比例因子調整時間
                        sleep_time = time_diff * scale_factor
                        
                        # 限制最大等待時間為1秒，防止過長等待
                        sleep_time = min(sleep_time, 1.0)
                        
                        # 只有在時間差為正數時才等待
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                    except (ValueError, TypeError) as e:
                        # 如果時間解析失敗，使用最小延遲
                        logger.warning(f"時間解析錯誤: {e} (記錄 {i+1}/{total_records})")
                        await asyncio.sleep(0.001)
                
                # 記錄當前時間作為下一次比較的基準
                last_time = current_time
                
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


@router.websocket("/ws/tick/{stock_id}/{date}/{scale}")
async def websocket_tick_data_with_scale(
    websocket: WebSocket, 
    stock_id: str, 
    date: str,
    scale: float,
    tick_service: TWStockTickService = Depends(get_tick_service),
    calculate_volumes: bool = True
):
    """
    WebSocket端點，用於訂閱特定股票和日期的Tick數據流，並可調整時間比例
    
    參數:
        websocket: WebSocket連接
        stock_id: 股票代碼
        date: 日期 (YYYYMMDD, YYYY-MM-DD, 或 YYYY/MM/DD 格式)
        scale: 時間比例因子 (1.0為實時，小於1.0加快，大於1.0減慢)
        tick_service: TWStockTickService實例
        calculate_volumes: 是否計算單次成交量 (預設為True)
    """
    # 確保比例因子為正數
    scale_factor = max(0.0001, float(scale))
    
    # 調用原始端點
    await websocket_tick_data(websocket, stock_id, date, tick_service, scale_factor, calculate_volumes)


@router.websocket("/ws/tick/{stock_id}/{date}/{scale}/{calculate_vol}")
async def websocket_tick_data_full_options(
    websocket: WebSocket, 
    stock_id: str, 
    date: str,
    scale: float,
    calculate_vol: str,
    tick_service: TWStockTickService = Depends(get_tick_service)
):
    """
    WebSocket端點，用於訂閱特定股票和日期的Tick數據流，可調整時間比例和是否計算單次成交量
    
    參數:
        websocket: WebSocket連接
        stock_id: 股票代碼
        date: 日期 (YYYYMMDD, YYYY-MM-DD, 或 YYYY/MM/DD 格式)
        scale: 時間比例因子 (1.0為實時，小於1.0加快，大於1.0減慢)
        calculate_vol: 是否計算單次成交量 ("true"或"false")
        tick_service: TWStockTickService實例
    """
    # 確保比例因子為正數
    scale_factor = max(0.0001, float(scale))
    
    # 解析是否計算單次成交量
    calculate_volumes = calculate_vol.lower() in ["true", "1", "yes", "y"]
    
    # 調用原始端點
    await websocket_tick_data(websocket, stock_id, date, tick_service, scale_factor, calculate_volumes)


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