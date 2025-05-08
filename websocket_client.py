#!/usr/bin/env python
"""
Taiwan Stock Tick WebSocket 客戶端

這個客戶端用於訂閱特定股票在特定日期的 Tick 數據，並即時接收數據。
"""

import asyncio
import websockets
import json
import argparse
import logging
from datetime import datetime
import pandas as pd
import os
import sys

# 設定日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("tw_stock_client")

async def subscribe_to_tick_data(stock_id: str, date: str, server_url: str, save_csv: bool = False, output_dir: str = None):
    """
    訂閱特定股票和日期的實時 tick 數據
    
    參數:
        stock_id: 股票代碼
        date: 日期 (YYYYMMDD 格式)
        server_url: WebSocket 服務器 URL (不包含路徑)
        save_csv: 是否保存接收到的數據到 CSV 文件
        output_dir: 輸出目錄，如果 save_csv 為 True 則必須提供
    """
    ws_url = f"{server_url}/ws/tick/{stock_id}/{date}"
    
    # 準備存儲接收到的數據
    all_data = []
    
    try:
        logger.info(f"嘗試連接到: {ws_url}")
        
        async with websockets.connect(ws_url) as websocket:
            logger.info(f"已連接到 {ws_url}")
            
            # 計算統計信息
            tick_count = 0
            start_time = datetime.now()
            
            # 持續接收數據
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                print(data)
                # 檢查是否為錯誤消息
                if "error" in data:
                    logger.error(f"服務器返回錯誤: {data['error']}")
                    break
                
                # 檢查是否為信息消息
                if "type" in data and data["type"] == "info":
                    logger.info(f"服務器信息: {data['message']}")
                    continue
                
                # 檢查是否為完成消息
                if "type" in data and data["type"] == "completed":
                    logger.info(f"數據流結束: {data['message']}")
                    
                    # 顯示服務器統計信息
                    if "stats" in data:
                        stats = data["stats"]
                        logger.info(f"服務器統計: 總記錄數={stats['total_records']}, "
                                   f"耗時={stats['elapsed_seconds']:.2f}秒, "
                                   f"速率={stats['records_per_second']:.2f}條/秒")
                    break
                
                # 處理 tick 數據
                tick_count += 1
                
                # 如果 data 中有 _meta，進行特殊處理，避免存入 CSV
                meta_info = data.pop("_meta", None)
                
                # 保存數據以便後續處理
                if save_csv:
                    all_data.append(data)
                
                # 顯示進度信息
                if meta_info and meta_info.get("record_number", 0) % 1000 == 0:
                    progress = meta_info.get("progress", 0)
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = tick_count / elapsed if elapsed > 0 else 0
                    logger.info(f"已接收 {tick_count} 條數據，進度: {progress:.2f}%, 速率: {rate:.2f} 條/秒")
                
                # 每 10000 條打印一條樣本數據
                if tick_count % 10000 == 1:
                    logger.info(f"樣本數據: {json.dumps(data, ensure_ascii=False)[:200]}...")
            
            # 顯示最終統計信息
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = tick_count / elapsed if elapsed > 0 else 0
            logger.info(f"接收完成，共 {tick_count} 條數據，用時 {elapsed:.2f} 秒，平均速率: {rate:.2f} 條/秒")
            
            # 保存數據到 CSV 文件
            if save_csv and all_data:
                if not output_dir:
                    output_dir = "."
                os.makedirs(output_dir, exist_ok=True)
                
                output_file = os.path.join(output_dir, f"{stock_id}_{date}_tick.csv")
                df = pd.DataFrame(all_data)
                df.to_csv(output_file, index=False)
                logger.info(f"數據已保存到: {output_file}")
    
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"連接已關閉: {e}")
    except Exception as e:
        logger.error(f"發生錯誤: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Taiwan Stock Tick Data WebSocket Client')
    parser.add_argument('--stock', '-s', required=True, help='股票代碼')
    parser.add_argument('--date', '-d', required=True, help='日期 (YYYYMMDD 格式)')
    parser.add_argument('--server', '-u', default='ws://localhost:8000', help='WebSocket 服務器 URL')
    parser.add_argument('--save', '-o', action='store_true', help='保存數據到 CSV 文件')
    parser.add_argument('--output-dir', '-p', help='CSV 輸出目錄路徑')
    
    args = parser.parse_args()
    
    # 驗證參數
    if args.save and not args.output_dir:
        logger.error("如果啟用 --save，必須提供 --output-dir 參數")
        sys.exit(1)
    
    try:
        asyncio.run(subscribe_to_tick_data(args.stock, args.date, args.server, args.save, args.output_dir))
    except KeyboardInterrupt:
        logger.info("用戶中斷，正在退出...")
    except Exception as e:
        logger.error(f"運行時錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()