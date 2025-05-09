"""
Tick 資料 API 端點模塊
提供 Taiwan Stock Tick API 的所有 REST API 端點
"""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from typing import List, Dict, Optional, Any
import logging
import pandas as pd
import numpy as np
import json
from datetime import datetime
from decimal import Decimal

from app.services.tick_api import TWStockTickService
from app.services.utils.price_utils import round_to_tick_size, process_price_columns, process_volume_columns
from app.core.config import settings

# 創建 API 路由器
router = APIRouter(
    prefix="/tick-data",
    tags=["Tick Data"]
)

# 取得 logger 實例
logger = logging.getLogger("tw_stock_api")

# 服務單例（Singleton）
_service = None

def get_tick_service() -> TWStockTickService:
    """
    返回 TWStockTickService 的單例實例
    使用單例模式確保整個應用程序中只有一個服務實例
    
    返回:
        TWStockTickService: 服務實例
    """
    global _service
    if _service is None:
        _service = TWStockTickService(
            api_key=settings.TW_STOCK_API_KEY,
            host=settings.TW_STOCK_API_HOST,
            port=settings.TW_STOCK_API_PORT,
            data_root=settings.TW_STOCK_DATA_ROOT
        )
    return _service

def convert_decimal(obj):
    """
    遞迴轉換對象中的 Decimal 為 float，以及 NaN/Infinity 為 None
    
    參數:
        obj: 要轉換的對象
        
    返回:
        轉換後的對象
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal(item) for item in obj]
    else:
        return obj

def custom_process_price_columns(df, columns=None):
    """
    自定義處理價格欄位，處理空字串的情況
    
    參數:
        df: 包含價格數據的 DataFrame
        columns: 要處理的列名列表，如果為 None，使用默認的價格列
        
    返回:
        處理後的 DataFrame
    """
    if df.empty:
        return df
        
    # 預設價格欄位
    if columns is None:
        columns = [
            'bp_best_1', 'bp_best_2', 'bp_best_3', 'bp_best_4', 'bp_best_5', 
            'sp_best_1', 'sp_best_2', 'sp_best_3', 'sp_best_4', 'sp_best_5', 
            'trade_price'
        ]
    
    # 只處理存在於 DataFrame 中的欄位
    existing_columns = [col for col in columns if col in df.columns]
    
    for col in existing_columns:
        try:
            # 只對非空值應用四捨五入
            df[col] = df[col].apply(
                lambda x: float(round_to_tick_size(x)) if x != "" and pd.notna(x) else x
            )
        except Exception as e:
            logger.error(f"處理價格欄位 {col} 時出錯: {e}")
    
    return df

def custom_process_volume_columns(df, columns=None):
    """
    自定義處理交易量欄位，處理空字串的情況
    
    參數:
        df: 包含交易量數據的 DataFrame
        columns: 要處理的列名列表，如果為 None，使用默認的交易量列
        
    返回:
        處理後的 DataFrame
    """
    if df.empty:
        return df
        
    # 預設交易量欄位
    if columns is None:
        columns = [
            'bv_best_1', 'bv_best_2', 'bv_best_3', 'bv_best_4', 'bv_best_5',
            'sv_best_1', 'sv_best_2', 'sv_best_3', 'sv_best_4', 'sv_best_5',
            'trade_volume'
        ]
    
    # 只處理存在於 DataFrame 中的欄位
    existing_columns = [col for col in columns if col in df.columns]
    
    for col in existing_columns:
        try:
            # 只對非空值應用轉換
            df[col] = df[col].apply(
                lambda x: int(x) if x != "" and pd.notna(x) else x
            )
        except Exception as e:
            logger.error(f"處理交易量欄位 {col} 時出錯: {e}")
    
    return df

def calculate_trade_volume(df):
    """
    計算每筆成交的單次成交量
    根據累積成交量(acc_transaction_volume)計算每筆match_flag="Y"的單次成交量(trade_volume)
    
    參數:
        df: 包含 Tick 數據的 DataFrame
        
    返回:
        添加了 trade_volume 欄位的 DataFrame
    """
    if df.empty or 'acc_transaction_volume' not in df.columns:
        return df
    
    # 創建一份數據的複本，避免修改原始數據
    result_df = df.copy()
    
    # 確保有 match_flag 欄位
    if 'match_flag' not in result_df.columns:
        # 如果沒有 match_flag 欄位，假設所有記錄都是成交記錄
        result_df['match_flag'] = 'Y'
    
    # 添加 trade_volume 欄位
    result_df['trade_volume'] = 0
    
    # 只處理成交記錄
    match_rows = result_df[result_df['match_flag'] == 'Y']
    
    if match_rows.empty:
        return result_df
    
    # 將 DataFrame 排序，確保按時間順序處理
    match_rows = match_rows.sort_values(by=['display_date', 'display_time'])
    
    # 初始化上一次成交的累積量
    last_acc_volume = 0
    
    # 計算每筆交易的單次成交量
    for idx, row in match_rows.iterrows():
        current_acc_volume = row['acc_transaction_volume']
        
        # 跳過無效值
        if pd.isna(current_acc_volume):
            continue
        
        # 第一筆交易或上一次成交量為0
        if last_acc_volume == 0:
            result_df.at[idx, 'trade_volume'] = current_acc_volume
        else:
            # 計算差值作為單次成交量
            result_df.at[idx, 'trade_volume'] = current_acc_volume - last_acc_volume
        
        # 更新上一次成交的累積量
        last_acc_volume = current_acc_volume
    
    return result_df

@router.get(
    "/{stock_id}/date/{date}",
    summary="取得特定日期的 tick 資料",
    description="返回指定股票在特定日期的 tick 資料"
)
async def get_tick_data_by_date(
    stock_id: str,
    date: str,
    convert_formats: bool = Query(True, description="是否轉換資料格式（日期、時間、價格）"),
    calculate_volumes: bool = Query(True, description="是否計算單次成交量"),
    service: TWStockTickService = Depends(get_tick_service)
):
    """
    取得特定股票在特定日期的 tick 資料
    
    此端點允許用戶獲取指定股票在某一特定日期的所有 tick 資料。
    用戶可以選擇是否將資料格式轉換為更易讀的形式，以及是否計算單次成交量。
    
    參數:
        stock_id: 股票代碼 (例如：'2330')
        date: 日期 (格式: 'YYYY-MM-DD', 'YYYY/MM/DD' 或 'YYYYMMDD')
        convert_formats: 是否轉換資料格式 (預設為 True)
        calculate_volumes: 是否計算單次成交量 (預設為 True)
        service: TW股票Tick服務實例 (自動注入)
        
    返回:
        包含 tick 資料的 JSON 回應
        
    錯誤:
        400: 參數無效
        500: 服務器內部錯誤
    """
    try:
        # 使用 get_tick_data 方法，將相同的日期作為開始和結束日期
        df = service.get_tick_data(
            stock_id=stock_id,
            start_date=date,
            end_date=date,
            convert_formats=convert_formats
        )
        
        # 處理資料格式
        if not df.empty:
            # 替換 NaN、Infinity 值為 None
            df = df.replace([np.inf, -np.inf, np.nan], None)
            
            # 使用自定義函數處理價格和交易量欄位
            if convert_formats:
                df = custom_process_price_columns(df)
                df = custom_process_volume_columns(df)
            
            # 計算單次成交量
            if calculate_volumes:
                df = calculate_trade_volume(df)
            
            # 轉換為字典列表
            records = df.to_dict('records')
            
            # 處理 Decimal 類型
            data = convert_decimal(records)
        else:
            data = []
        
        # 構建回應
        response = {
            "status": "success",
            "message": "成功獲取 tick 資料" if data else "未找到資料",
            "data": data,
            "count": len(data),
            "stock_id": stock_id,
            "date": date,
            "convert_formats": convert_formats,
            "calculate_volumes": calculate_volumes,
            "timestamp": datetime.now().isoformat()
        }
        
        # 確保回應可以被序列化
        return response
        
    except ValueError as e:
        # 處理參數錯誤
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e)}
        )
    except Exception as e:
        # 處理未知錯誤
        logger.error(f"獲取股票 {stock_id} 在日期 {date} 的 tick 資料時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"獲取 tick 資料時發生錯誤: {str(e)}"}
        )

@router.get(
    "/{stock_id}/range/{start_date}/{end_date}",
    summary="取得日期範圍內的 tick 資料",
    description="返回指定股票在指定日期範圍內的 tick 資料"
)
async def get_tick_data_by_range(
    stock_id: str,
    start_date: str,
    end_date: str,
    convert_formats: bool = Query(True, description="是否轉換資料格式（日期、時間、價格）"),
    calculate_volumes: bool = Query(True, description="是否計算單次成交量"),
    service: TWStockTickService = Depends(get_tick_service)
):
    """
    取得特定股票在日期範圍內的 tick 資料
    
    此端點允許用戶獲取指定股票在某個日期範圍內的所有 tick 資料。
    用戶可以選擇是否將資料格式轉換為更易讀的形式，以及是否計算單次成交量。
    
    參數:
        stock_id: 股票代碼 (例如：'2330')
        start_date: 開始日期 (格式: 'YYYY-MM-DD', 'YYYY/MM/DD' 或 'YYYYMMDD')
        end_date: 結束日期 (格式同上)
        convert_formats: 是否轉換資料格式 (預設為 True)
        calculate_volumes: 是否計算單次成交量 (預設為 True)
        service: TW股票Tick服務實例 (自動注入)
        
    返回:
        包含 tick 資料的 JSON 回應
        
    錯誤:
        400: 參數無效
        500: 服務器內部錯誤
    """
    try:
        # 從服務中獲取資料
        df = service.get_tick_data(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            convert_formats=convert_formats
        )
        
        # 處理資料格式
        if not df.empty:
            # 替換 NaN、Infinity 值為 None
            df = df.replace([np.inf, -np.inf, np.nan], None)
            
            # 使用自定義函數處理價格和交易量欄位
            if convert_formats:
                df = custom_process_price_columns(df)
                df = custom_process_volume_columns(df)
            
            # 計算單次成交量
            if calculate_volumes:
                df = calculate_trade_volume(df)
            
            # 轉換為字典列表
            records = df.to_dict('records')
            
            # 處理 Decimal 類型
            data = convert_decimal(records)
        else:
            data = []
        
        # 構建回應
        response = {
            "status": "success",
            "message": "成功獲取 tick 資料" if data else "未找到資料",
            "data": data,
            "count": len(data),
            "stock_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "convert_formats": convert_formats,
            "calculate_volumes": calculate_volumes,
            "timestamp": datetime.now().isoformat()
        }
        
        # 返回回應
        return response
        
    except ValueError as e:
        # 處理參數錯誤
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e)}
        )
    except Exception as e:
        # 處理未知錯誤
        logger.error(f"獲取股票 {stock_id} 在日期範圍 {start_date} 至 {end_date} 的 tick 資料時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"獲取 tick 資料時發生錯誤: {str(e)}"}
        )

@router.get(
    "/price/round/{price}",
    summary="股票價格四捨五入",
    description="依據台灣證券交易所規則對價格進行四捨五入"
)
async def round_price(
    price: float
):
    """
    依據台灣證券交易所規則對價格進行四捨五入
    
    此端點允許用戶對任意價格值應用台灣證券交易所的價格檔位規則。
    
    參數:
        price: 要四捨五入的價格
        
    返回:
        包含原始價格和四捨五入後價格的 JSON 回應
        
    錯誤:
        500: 服務器內部錯誤
    """
    try:
        # 直接使用 price_utils.py 中的 round_to_tick_size 函數
        rounded_price = round_to_tick_size(price)
        # 將 Decimal 轉換為 float
        return {
            "original_price": price,
            "rounded_price": float(rounded_price),
            "message": f"價格 {price} 四捨五入為 {rounded_price}"
        }
    except Exception as e:
        logger.error(f"價格四捨五入過程中發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"價格四捨五入過程中發生錯誤: {str(e)}"}
        )