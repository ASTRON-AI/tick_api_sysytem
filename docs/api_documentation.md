# Taiwan Stock Tick API 文檔

本文檔詳細說明了 Taiwan Stock Tick API 的功能和使用方法。

## API 概述

Taiwan Stock Tick API 提供了台灣股票市場的 Tick 級數據，支持以下功能：

- 獲取特定股票在特定日期的 Tick 數據
- 獲取特定股票在日期範圍內的 Tick 數據
- 根據台灣證券交易所規則對價格進行四捨五入
- 透過 WebSocket 實時訂閱 Tick 數據流

## RESTful API 端點

### 獲取特定日期的 Tick 數據

```
GET /api/v1/tick-data/{stock_id}/date/{date}
```

**參數：**

- `stock_id`: 股票代碼（例如：2330）
- `date`: 日期，支持多種格式（YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD）
- `convert_formats`: 是否轉換日期、時間和價格格式（可選，默認為 true）

**示例請求：**

```
GET /api/v1/tick-data/2330/date/20240507?convert_formats=true
```

**示例響應：**

```json
{
  "status": "success",
  "message": "成功獲取 tick 資料",
  "data": [
    {
      "code": "2330",
      "display_date": "2024-05-07",
      "display_time": "09:00:01.123",
      "trade_price": 850.0,
      "trade_volume": 1000,
      "bp_best_1": 849.5,
      "bv_best_1": 2000,
      "sp_best_1": 850.5,
      "sv_best_1": 1500,
      "... 其他欄位 ...": "..."
    },
    "... 更多數據 ..."
  ],
  "count": 42500,
  "stock_id": "2330",
  "date": "20240507",
  "convert_formats": true,
  "timestamp": "2024-05-08T12:34:56.789"
}
```

### 獲取日期範圍內的 Tick 數據

```
GET /api/v1/tick-data/{stock_id}/range/{start_date}/{end_date}
```

**參數：**

- `stock_id`: 股票代碼（例如：2330）
- `start_date`: 開始日期（YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD）
- `end_date`: 結束日期（YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD）
- `convert_formats`: 是否轉換日期、時間和價格格式（可選，默認為 true）

**示例請求：**

```
GET /api/v1/tick-data/2330/range/20240501/20240507?convert_formats=true
```

**示例響應：**

```json
{
  "status": "success",
  "message": "成功獲取 tick 資料",
  "data": [
    "... 數據數組，與上一個端點格式相同 ..."
  ],
  "count": 295000,
  "stock_id": "2330",
  "start_date": "20240501",
  "end_date": "20240507",
  "convert_formats": true,
  "timestamp": "2024-05-08T12:34:56.789"
}
```

### 股票價格四捨五入

```
GET /api/v1/tick-data/price/round/{price}
```

**參數：**

- `price`: 要四捨五入的價格

**示例請求：**

```
GET /api/v1/tick-data/price/round/123.45
```

**示例響應：**

```json
{
  "original_price": 123.45,
  "rounded_price": 123.5,
  "message": "價格 123.45 四捨五入為 123.5"
}
```

## WebSocket API

WebSocket API 允許客戶端實時訂閱特定股票在特定日期的 Tick 數據流。每條數據會以每 1 毫秒的速率發送。

### Tick 數據訂閱

```
WebSocket: /ws/tick/{stock_id}/{date}
```

**參數：**

- `stock_id`: 股票代碼（例如：2330）
- `date`: 日期（YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD）

**連接示例：**

```
ws://your-server:8000/ws/tick/2330/20240508
```

### WebSocket 協議和消息格式

1. **信息消息**：

WebSocket 連接建立後，服務器會發送一條信息消息，包含總記錄數：

```json
{
  "type": "info", 
  "message": "開始數據流，總記錄數: 42500", 
  "total_records": 42500
}
```

2. **數據消息**：

之後服務器會開始發送 Tick 數據消息，每條消息包含一個 tick 數據：

```json
{
  "code": "2330",
  "display_date": "2024-05-08",
  "display_time": "09:00:01.123",
  "trade_price": 850.0,
  "trade_volume": 1000,
  "bp_best_1": 849.5,
  "bv_best_1": 2000,
  "sp_best_1": 850.5,
  "sv_best_1": 1500,
  "... 其他欄位 ...": "...",
  "_meta": {
    "record_number": 1,
    "total_records": 42500,
    "progress": 0.0024
  }
}
```

3. **完成消息**：

當所有數據發送完畢後，服務器會發送一條完成消息：

```json
{
  "type": "completed", 
  "message": "所有 tick 數據已發送完畢",
  "stats": {
    "total_records": 42500,
    "elapsed_seconds": 42.5,
    "records_per_second": 1000.0
  }
}
```

4. **錯誤消息**：

如果發生錯誤，服務器會發送一條錯誤消息：

```json
{
  "error": "無法獲取股票 2330 在 20240508 的數據"
}
```

### WebSocket 心跳

為了保持長連接的活躍，可以使用心跳端點：

```
WebSocket: /ws/heartbeat
```

連接到此端點後，服務器會每隔 `WS_HEARTBEAT_INTERVAL` 秒（默認為 30 秒）發送一條心跳消息：

```json
{
  "type": "heartbeat",
  "timestamp": "2024-05-08T12:34:56.789"
}
```

## 客戶端示例

### 基本 WebSocket 客戶端

以下是一個簡單的 Python WebSocket 客戶端示例：

```python
import asyncio
import websockets
import json

async def subscribe_to_tick_data(stock_id, date, server_url):
    ws_url = f"{server_url}/ws/tick/{stock_id}/{date}"
    
    async with websockets.connect(ws_url) as websocket:
        print(f"已連接到 {ws_url}")
        
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            if "error" in data:
                print(f"錯誤: {data['error']}")
                break
                
            if "type" in data and data["type"] == "completed":
                print(f"數據流結束: {data['message']}")
                break
                
            # 處理 tick 數據
            print(data)

# 使用示例
asyncio.run(subscribe_to_tick_data("2330", "20240508", "ws://localhost:8000"))
```

### 帶圖形界面的客戶端

我們還提供了一個帶圖形界面的客戶端示例，可以實時顯示價格和成交量圖表。請查看 `examples` 目錄下的 `websocket_gui_client.py`。

## 數據欄位說明

Tick 數據包含以下主要欄位：

- `code`: 股票代碼
- `display_date`: 日期
- `display_time`: 時間（毫秒級）
- `trade_price`: 成交價格
- `trade_volume`: 成交量
- `bp_best_1` ~ `bp_best_5`: 最佳五檔買價
- `bv_best_1` ~ `bv_best_5`: 最佳五檔買量
- `sp_best_1` ~ `sp_best_5`: 最佳五檔賣價
- `sv_best_1` ~ `sv_best_5`: 最佳五檔賣量

## 錯誤處理

API 返回的錯誤格式如下：

```json
{
  "detail": {
    "message": "錯誤信息"
  }
}
```

常見錯誤包括：

- 400 Bad Request: 參數無效
- 404 Not Found: 資源不存在
- 500 Internal Server Error: 服務器內部錯誤

## 限制和注意事項

- 數據範圍限制：可用的歷史數據從 2020 年 3 月 2 日開始
- 請求頻率限制：每分鐘最多 60 個請求
- WebSocket 連接限制：每個 IP 地址最多同時 10 個 WebSocket 連接