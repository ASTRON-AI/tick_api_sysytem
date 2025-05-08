import requests
import json
import pandas as pd
import time
import http.client
from datetime import datetime, timedelta
from typing import Dict, List, Union, Optional, Any, Callable
import logging
import os
import asyncio
import threading
from queue import Queue
from decimal import Decimal

from app.core.config import settings
from app.services.utils.price_utils import round_to_tick_size, process_price_columns, process_volume_columns
from app.services.utils.date_time_utils import (
    format_date_to_yyyymmdd, 
    format_time_to_hhmmss, 
    convert_timestamp_to_date,
    format_display_time,
    get_date_range_files,
    process_date_time_columns
)

class TWStockTickService:
    """
    Taiwan Stock Market Tick Data Service (Enhanced Version)
    
    A service for accessing and managing Taiwan stock market tick data,
    providing methods to fetch historical data and subscribe to real-time updates.
    Includes enhanced features for price rounding and time formatting.
    """
    
    def __init__(self, 
                api_key: str = None, 
                host: str = None, 
                port: int = None,
                data_root: str = None):
        """
        Initialize the Taiwan Stock Tick Service
        
        Args:
            api_key: API key for authentication (defaults to config value)
            host: Server hostname (defaults to config value)
            port: Server port (defaults to config value)
            data_root: Data directory path (defaults to config value)
        """
        self.api_key = api_key or settings.TW_STOCK_API_KEY
        self.host = host or settings.TW_STOCK_API_HOST
        self.port = port or settings.TW_STOCK_API_PORT
        self.data_root = data_root or settings.TW_STOCK_DATA_ROOT
        
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        
        # Get logger instance
        self.logger = logging.getLogger("tw_stock_api")
        
        # Subscription management
        self._subscriptions = {}  # {stock_id: [callback1, callback2, ...]}
        self._subscription_thread = None
        self._subscription_active = False
        self._subscription_queue = Queue()
        
        self.logger.info(f"TWStockTickService initialized with host={self.host}, port={self.port}")
    
    def _execute_query(self, sql: str) -> Any:
        """
        Execute SQL query against the Taiwan Stock API
        
        Args:
            sql: SQL query string
            
        Returns:
            Query result as list/dict
            
        Raises:
            Exception: For various query execution errors
        """
        try:
            conn = http.client.HTTPConnection(self.host, self.port)
            payload = json.dumps({
                "sql": sql,
                "type": "json"
            })
            
            self.logger.debug(f"Sending query: {sql}")
            
            conn.request("POST", "/", payload, self.headers)
            res = conn.getresponse()
            data = res.read()
            response_text = data.decode("utf-8")
            
            # Check if response is empty
            if not response_text.strip():
                self.logger.warning("Server returned empty response")
                return []
                
            try:
                # Try to parse JSON
                result = json.loads(response_text)
                return result
            except json.JSONDecodeError as e:
                # Log error and response preview
                preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
                self.logger.error(f"JSON parse error: {e}. Response preview: {preview}")
                raise
                
        except Exception as e:
            self.logger.error(f"Error during query execution: {e}")
            self.logger.exception("Detailed error information:")
            raise
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_tick_data(self, 
                     stock_id: str, 
                     start_date: str, 
                     end_date: str, 
                     start_time: Optional[str] = None, 
                     end_time: Optional[str] = None,
                     convert_formats: bool = True) -> pd.DataFrame:
        """
        Get tick data for a specific stock in the given date and time range
        
        Args:
            stock_id: Stock ID (e.g. '2330')
            start_date: Start date (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
            end_date: End date (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
            start_time: Start time (optional, HH:MM:SS, HHMMSS, HH:MM, or HHMM)
            end_time: End time (optional, HH:MM:SS, HHMMSS, HH:MM, or HHMM)
            convert_formats: Whether to convert data formats (dates, times, prices)
            
        Returns:
            DataFrame containing tick data
            
        Raises:
            ValueError: For various validation errors
            Exception: For query execution errors
        """
        try:
            # 驗證股票代碼
            if not stock_id or not isinstance(stock_id, str):
                raise ValueError("Stock ID must be a non-empty string")
                
            stock_id = stock_id.strip()
            # 移除對純數字的限制，改為檢查股票代碼是否符合台灣市場規範
            if not stock_id or len(stock_id) > 10:  # 台灣股票代碼通常不超過6位，但為了兼容性給寬鬆一些
                raise ValueError(f"Invalid stock ID format: {stock_id}")
            
            # Get all files for the date range
            files = get_date_range_files(self.data_root, start_date, end_date)
            
            if not files:
                self.logger.warning("No available data for the specified date range")
                return pd.DataFrame()
            
            all_results = []
            
            for file_path in files:
                try:
                    # Build query for individual file
                    sql = f"SELECT * FROM read_parquet('{file_path}') WHERE code = '{stock_id}'"
                    
                    # Add time filtering conditions
                    formatted_start_time = format_time_to_hhmmss(start_time)
                    formatted_end_time = format_time_to_hhmmss(end_time)
                    
                    if formatted_start_time:
                        sql += f" AND CAST(substring(display_time, 1, 6) AS INT) >= {formatted_start_time}"
                        
                    if formatted_end_time:
                        sql += f" AND CAST(substring(display_time, 1, 6) AS INT) <= {formatted_end_time}"
                    
                    # Execute query
                    self.logger.info(f"Querying file: {os.path.basename(file_path)}")
                    file_result = self._execute_query(sql)
                    
                    if file_result and isinstance(file_result, list) and len(file_result) > 0:
                        all_results.extend(file_result)
                        self.logger.info(f"Retrieved {len(file_result)} records")
                    else:
                        self.logger.info(f"No matching data in file {os.path.basename(file_path)}")
                except Exception as e:
                    self.logger.error(f"Error processing file {os.path.basename(file_path)}: {e}")
                    # Continue processing other files
            
            # Merge all results
            if all_results:
                df = pd.DataFrame(all_results)
                
                # Process date and time formats
                df = process_date_time_columns(df, convert_formats)
                
                # Process price and volume data if requested
                if convert_formats:
                    df = process_price_columns(df)
                    df = process_volume_columns(df)
                    
                # Sort data
                df = df.sort_values(by=['display_date', 'display_time'])
                
                self.logger.info(f"Successfully retrieved a total of {len(df)} data records")
                return df
            else:
                self.logger.warning("No matching data found")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Unexpected error while retrieving tick data: {e}")
            self.logger.exception("Detailed error information:")
            raise
    
    def get_tick_data_by_date(self, 
                             stock_id: str, 
                             date: str,
                             start_time: Optional[str] = None, 
                             end_time: Optional[str] = None,
                             convert_formats: bool = True) -> pd.DataFrame:
        """
        Get tick data for a specific stock on a single date
        
        Args:
            stock_id: Stock ID (e.g. '2330')
            date: Date (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
            start_time: Start time (optional, HH:MM:SS, HHMMSS, HH:MM, or HHMM)
            end_time: End time (optional, HH:MM:SS, HHMMSS, HH:MM, or HHMM)
            convert_formats: Whether to convert data formats (dates, times, prices)
            
        Returns:
            DataFrame containing tick data
            
        Raises:
            ValueError: For various validation errors
            Exception: For query execution errors
        """
        try:
            # 驗證股票代碼
            if not stock_id or not isinstance(stock_id, str):
                raise ValueError("Stock ID must be a non-empty string")
                
            stock_id = stock_id.strip()
            # 移除對純數字的限制，改為檢查股票代碼是否符合台灣市場規範
            if not stock_id or len(stock_id) > 10:
                raise ValueError(f"Invalid stock ID format: {stock_id}")
            
            # Format date
            formatted_date = format_date_to_yyyymmdd(date)
            
            # Build file path
            file_path = os.path.join(self.data_root, f'tw_orderbook_{formatted_date}.parquet')
            
            # Build SQL query
            sql = f"SELECT * FROM read_parquet('{file_path}') WHERE code = '{stock_id}'"
            
            # Add time filtering conditions
            formatted_start_time = format_time_to_hhmmss(start_time)
            formatted_end_time = format_time_to_hhmmss(end_time)
            
            if formatted_start_time:
                sql += f" AND CAST(substring(display_time, 1, 6) AS INT) >= {formatted_start_time}"
                
            if formatted_end_time:
                sql += f" AND CAST(substring(display_time, 1, 6) AS INT) <= {formatted_end_time}"
                
            # Add sorting
            sql += " ORDER BY display_time"
            
            self.logger.info(f"Requesting tick data for stock {stock_id} on {date}")
            
            # Execute query
            result = self._execute_query(sql)
            
            if not result:
                self.logger.warning("Query result is empty")
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = pd.DataFrame(result)
            
            # Process date and time formats
            df = process_date_time_columns(df, convert_formats)
            
            # Process price and volume data if requested
            if convert_formats:
                df = process_price_columns(df)
                df = process_volume_columns(df)
                
            self.logger.info(f"Successfully retrieved {len(df)} data records")
            return df
                
        except Exception as e:
            self.logger.error(f"Unexpected error while retrieving tick data: {e}")
            self.logger.exception("Detailed error information:")
            raise
    
    def add_subscription(self, stock_id: str, callback: Callable[[pd.DataFrame], None], convert_formats: bool = True) -> bool:
        """
        Add a subscription for a specific stock
        
        Args:
            stock_id: Stock ID (e.g. '2330')
            callback: Callback function to process new tick data
            convert_formats: Whether to convert data formats (dates, times, prices)
            
        Returns:
            True if subscription was added successfully
            
        Raises:
            ValueError: For invalid stock ID
        """
        # 驗證股票代碼
        if not stock_id or not isinstance(stock_id, str):
            raise ValueError("Stock ID must be a non-empty string")
            
        stock_id = stock_id.strip()
        # 移除對純數字的限制，改為檢查股票代碼是否符合台灣市場規範
        if not stock_id or len(stock_id) > 10:
            raise ValueError(f"Invalid stock ID format: {stock_id}")
        
        # Create subscription key with format flag
        sub_key = f"{stock_id}_{convert_formats}"
        
        # Add subscription
        if sub_key not in self._subscriptions:
            self._subscriptions[sub_key] = []
        
        # Add callback if not already in list
        if callback not in self._subscriptions[sub_key]:
            self._subscriptions[sub_key].append(callback)
            self.logger.info(f"Added subscription for stock {stock_id} with format conversion: {convert_formats}")
        
        # Store format conversion preference
        callback._convert_formats = convert_formats  # Attach attribute to callback
        
        # Start subscription thread if not already running
        if not self._subscription_active:
            self._start_subscription_thread()
        
        return True
    
    def remove_subscription(self, stock_id: str, callback: Optional[Callable] = None, convert_formats: Optional[bool] = None) -> bool:
        """
        Remove a subscription for a specific stock
        
        Args:
            stock_id: Stock ID (e.g. '2330')
            callback: Callback function to remove (if None, all callbacks for this stock are removed)
            convert_formats: Format conversion flag to match (if None, remove regardless of flag)
            
        Returns:
            True if subscription was removed successfully, False if not found
        """
        removed = False
        
        # If format flag not specified, remove from all format variants
        if convert_formats is None:
            keys_to_check = [f"{stock_id}_True", f"{stock_id}_False"]
        else:
            keys_to_check = [f"{stock_id}_{convert_formats}"]
        
        for sub_key in keys_to_check:
            if sub_key not in self._subscriptions:
                continue
                
            if callback is None:
                # Remove all subscriptions for this stock and format
                del self._subscriptions[sub_key]
                self.logger.info(f"Removed all subscriptions for {sub_key}")
                removed = True
            else:
                # Remove specific callback
                if callback in self._subscriptions[sub_key]:
                    self._subscriptions[sub_key].remove(callback)
                    self.logger.info(f"Removed subscription callback for {sub_key}")
                    removed = True
                    
                    # Remove stock entry if no more callbacks
                    if not self._subscriptions[sub_key]:
                        del self._subscriptions[sub_key]
        
        # Stop subscription thread if no more subscriptions
        if not self._subscriptions and self._subscription_active:
            self._stop_subscription_thread()
        
        return removed
    
    def _start_subscription_thread(self) -> None:
        """Start the subscription thread to poll for new data"""
        if self._subscription_active:
            return
        
        self._subscription_active = True
        self._subscription_thread = threading.Thread(target=self._subscription_worker)
        self._subscription_thread.daemon = True
        self._subscription_thread.start()
        self.logger.info("Subscription thread started")
    
    def _stop_subscription_thread(self) -> None:
        """Stop the subscription thread"""
        if not self._subscription_active:
            return
        
        self._subscription_active = False
        
        # Add stop signal to queue
        self._subscription_queue.put(None)
        
        if self._subscription_thread:
            self._subscription_thread.join(timeout=5)
            self._subscription_thread = None
            
        self.logger.info("Subscription thread stopped")
    
    def _subscription_worker(self) -> None:
        """Worker thread to poll for new data and handle subscriptions"""
        last_time_by_stock = {}  # {stock_id: last_time}
        
        while self._subscription_active:
            try:
                # Check for stop signal
                try:
                    signal = self._subscription_queue.get_nowait()
                    if signal is None:
                        break
                except Exception:
                    pass
                
                # Skip if no subscriptions
                if not self._subscriptions:
                    time.sleep(1)
                    continue
                
                # Current date
                today = datetime.now().strftime('%Y%m%d')
                
                # Group subscriptions by stock ID (ignoring format flag for querying)
                stock_subscriptions = {}
                for sub_key, callbacks in self._subscriptions.items():
                    stock_id = sub_key.split('_')[0]
                    if stock_id not in stock_subscriptions:
                        stock_subscriptions[stock_id] = []
                    stock_subscriptions[stock_id].extend(callbacks)
                
                # Check each subscribed stock
                for stock_id, callbacks in stock_subscriptions.items():
                    if not callbacks:  # Skip if no callbacks
                        continue
                        
                    try:
                        # Get last processed time for this stock
                        last_time = last_time_by_stock.get(stock_id, "000000")
                        
                        # Build file path
                        file_path = os.path.join(self.data_root, f'tw_orderbook_{today}.parquet')
                        
                        # Build SQL query
                        sql = f"SELECT * FROM read_parquet('{file_path}') WHERE code = '{stock_id}' AND CAST(substring(display_time, 1, 6) AS INT) > {last_time} ORDER BY display_time"
                        
                        # Execute query
                        result = self._execute_query(sql)
                        
                        if result and isinstance(result, list) and len(result) > 0:
                            # Convert to DataFrame
                            raw_df = pd.DataFrame(result)
                            
                            # Update last processed time
                            if 'display_time' in raw_df.columns and not raw_df.empty:
                                last_time_by_stock[stock_id] = raw_df['display_time'].iloc[-1][:6]
                            
                            # Group callbacks by format conversion preference
                            format_groups = {True: [], False: []}
                            for callback in callbacks:
                                convert_formats = getattr(callback, '_convert_formats', True)  # Default to True
                                format_groups[convert_formats].append(callback)
                            
                            # Process each format group separately
                            for convert_formats, format_callbacks in format_groups.items():
                                if not format_callbacks:  # Skip if no callbacks for this format
                                    continue
                                    
                                # Create a copy for this format group
                                df = raw_df.copy()
                                
                                # Apply format conversions if requested
                                if convert_formats:
                                    df = process_date_time_columns(df, True)
                                    df = process_price_columns(df)
                                    df = process_volume_columns(df)
                                
                                # Process callbacks
                                for callback in format_callbacks:
                                    try:
                                        callback(df)
                                    except Exception as e:
                                        self.logger.error(f"Error in callback for stock {stock_id}: {e}")
                                    
                    except Exception as e:
                        self.logger.error(f"Error processing subscription for stock {stock_id}: {e}")
                
                # Sleep to avoid excessive polling
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in subscription worker: {e}")
                time.sleep(5)
        
        self.logger.info("Subscription worker thread exiting")
    
    def get_latest_tick(self, stock_id: str, convert_formats: bool = True) -> Optional[Dict]:
        """
        Get the latest tick data for a specific stock
        
        Args:
            stock_id: Stock ID (e.g. '2330')
            convert_formats: Whether to convert data formats (dates, times, prices)
            
        Returns:
            Dictionary containing the latest tick data, or None if not found
        """
        try:
            # 驗證股票代碼
            if not stock_id or not isinstance(stock_id, str):
                raise ValueError("Stock ID must be a non-empty string")
                
            stock_id = stock_id.strip()
            # 移除對純數字的限制，改為檢查股票代碼是否符合台灣市場規範
            if not stock_id or len(stock_id) > 10:
                raise ValueError(f"Invalid stock ID format: {stock_id}")
            
            # Current date
            today = datetime.now().strftime('%Y%m%d')
            
            # Build file path
            file_path = os.path.join(self.data_root, f'tw_orderbook_{today}.parquet')
            
            # Build SQL query to get the latest record
            sql = f"SELECT * FROM read_parquet('{file_path}') WHERE code = '{stock_id}' ORDER BY display_time DESC LIMIT 1"
            
            # Execute query
            result = self._execute_query(sql)
            
            if result and isinstance(result, list) and len(result) > 0:
                # Get first (and only) result
                data = result[0]
                
                # Apply format conversions if requested
                if convert_formats:
                    # Convert date format
                    if 'display_date' in data:
                        data['display_date'] = convert_timestamp_to_date(data['display_date'])
                    
                    # Convert time format
                    if 'display_time' in data:
                        data['display_time'] = format_display_time(data['display_time'])
                    
                    # Round prices
                    price_columns = ['bp_best_1', 'bp_best_2', 'bp_best_3', 'bp_best_4', 'bp_best_5', 
                                   'sp_best_1', 'sp_best_2', 'sp_best_3', 'sp_best_4', 'sp_best_5', 
                                   'trade_price']
                    
                    for col in price_columns:
                        if col in data and data[col] is not None:
                            data[col] = float(round_to_tick_size(data[col]))
                    
                    # Convert volumes to integers
                    volume_columns = ['bv_best_1', 'bv_best_2', 'bv_best_3', 'bv_best_4', 'bv_best_5',
                                    'sv_best_1', 'sv_best_2', 'sv_best_3', 'sv_best_4', 'sv_best_5',
                                    'trade_volume']
                    
                    for col in volume_columns:
                        if col in data and data[col] is not None:
                            data[col] = int(data[col])
                
                return data
            else:
                self.logger.warning(f"No data found for stock {stock_id} today")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving latest tick data: {e}")
            self.logger.exception("Detailed error information:")
            raise
    
    def get_stock_list(self) -> List[str]:
        """
        Get a list of all available stock IDs
        
        Returns:
            List of stock IDs
        """
        try:
            # Current date
            today = datetime.now().strftime('%Y%m%d')
            
            # Try with today's date first
            file_path = os.path.join(self.data_root, f'tw_orderbook_{today}.parquet')
            
            # If today's file doesn't exist, try with yesterday's date
            if not os.path.exists(file_path):
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                file_path = os.path.join(self.data_root, f'tw_orderbook_{yesterday}.parquet')
            
            # If still no file, find the most recent file
            if not os.path.exists(file_path):
                # Find all parquet files
                files = [f for f in os.listdir(self.data_root) if f.startswith('tw_orderbook_') and f.endswith('.parquet')]
                
                if not files:
                    self.logger.warning("No data files found")
                    return []
                
                # Sort files by date (newest first)
                files.sort(reverse=True)
                file_path = os.path.join(self.data_root, files[0])
            
            # Build SQL query to get distinct stock IDs
            sql = f"SELECT DISTINCT code FROM read_parquet('{file_path}')"
            
            # Execute query
            result = self._execute_query(sql)
            
            if result and isinstance(result, list):
                return [item['code'] for item in result]
            else:
                self.logger.warning("No stock IDs found")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving stock list: {e}")
            self.logger.exception("Detailed error information:")
            raise
    
    def round_price(self, price: Union[float, Decimal, str]) -> Decimal:
        """
        Round a price to the nearest valid tick size based on Taiwan Stock Exchange rules
        
        Args:
            price: The price to round
            
        Returns:
            Rounded price according to Taiwan Stock Exchange rules
        """
        return round_to_tick_size(price)
    
    def __del__(self):
        """Cleanup on object destruction"""
        if self._subscription_active:
            self._stop_subscription_thread()
    
    # 在 TWStockTickService 類中添加此方法
    
    async def get_ws_tick_data(self, 
                            stock_id: str, 
                            date: str,
                            start_time: Optional[str] = None, 
                            end_time: Optional[str] = None,
                            convert_formats: bool = True) -> List[Dict[str, Any]]:
        """
        異步獲取 Tick 數據，專為 WebSocket 流設計。
        使用與 get_tick_data_by_date 相同的邏輯來獲取數據，確保一致性。
        
        參數:
            stock_id: 股票代碼
            date: 日期 (YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD)
            start_time: 開始時間 (可選, HH:MM:SS, HHMMSS, HH:MM, 或 HHMM)
            end_time: 結束時間 (可選, HH:MM:SS, HHMMSS, HH:MM, 或 HHMM)
            convert_formats: 是否轉換數據格式 (日期、時間、價格)
                
        返回:
            包含 Tick 數據的字典列表
                
        異常:
            ValueError: 參數無效
            Exception: 查詢執行錯誤
        """
        try:
            # 驗證股票代碼
            if not stock_id or not isinstance(stock_id, str):
                raise ValueError("股票代碼必須是非空字符串")
                    
            stock_id = stock_id.strip()
            # 移除對純數字的限制，改為檢查股票代碼是否符合台灣市場規範
            if not stock_id or len(stock_id) > 10:
                raise ValueError(f"無效的股票代碼格式: {stock_id}")
            
            # 使用現有的 get_tick_data 方法獲取數據
            # 將相同的日期作為開始和結束日期
            df = self.get_tick_data(
                stock_id=stock_id,
                start_date=date,
                end_date=date,
                start_time=start_time,
                end_time=end_time,
                convert_formats=convert_formats
            )
            
            if df.empty:
                self.logger.warning(f"沒有找到股票 {stock_id} 在日期 {date} 的數據")
                return []
            
            # 處理 NaN 值
            import pandas as pd
            import numpy as np
            df = df.replace([np.inf, -np.inf, np.nan], None)
            
            # 轉換為字典列表
            records = df.to_dict('records')
            
            # 處理 Decimal 類型
            def convert_decimal(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: convert_decimal(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimal(item) for item in obj]
                else:
                    return obj
            
            data_list = convert_decimal(records)
            
            self.logger.info(f"成功獲取股票 {stock_id} 在日期 {date} 的 {len(data_list)} 條數據記錄")
            return data_list
                
        except Exception as e:
            self.logger.error(f"獲取 WebSocket Tick 數據時發生錯誤: {e}")
            self.logger.exception("詳細錯誤信息:")
            raise