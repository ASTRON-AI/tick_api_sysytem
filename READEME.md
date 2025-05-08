# Taiwan Stock Tick API 服務

提供台灣股票市場 Tick 資料的 RESTful API 和 WebSocket 服務，具有價格四捨五入、時間格式轉換和即時數據流功能。

## 功能特色

- **歷史資料查詢**：按日期或日期範圍獲取特定股票的 Tick 資料
- **WebSocket 實時數據**：透過 WebSocket 訂閱特定股票特定日期的 Tick 資料流
- **價格四捨五入**：依據台灣證券交易所規則自動四捨五入價格
- **日期時間格式化**：將原始數值格式轉換為易讀格式
- **格式自訂選項**：支援原始格式或格式化後的資料
- **完整 API 文檔**：提供 Swagger UI 的全面 API 文檔
- **容器化部署**：使用 Docker 和 Docker Compose 輕鬆部署
- **強健的錯誤處理**：一致的錯誤回應與詳細資訊

## 啟動服務

### 環境準備

- Python 3.9+
- 按照 `requirements.txt` 安裝所需依賴

### 方法一：直接啟動

1. 複製環境變數設定檔：
   ```bash
   cp .env.example .env
   ```

2. 編輯 `.env` 檔案，設定你的環境變數：
   ```
   HOST=0.0.0.0
   PORT=8000
   DEBUG=True
   LOG_LEVEL=INFO
   CORS_ORIGINS=*
   TW_STOCK_API_KEY=你的API金鑰
   TW_STOCK_API_HOST=140.113.87.91
   TW_STOCK_API_PORT=3000
   TW_STOCK_DATA_ROOT=E:\\project\\tick raw data
   DEFAULT_CONVERT_FORMATS=True
   WS_HEARTBEAT_INTERVAL=30
   ```

3. 啟動服務：
   ```bash
   python main.py
   ```
   或使用 uvicorn：
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

### 方法二：使用 Docker

1. 進入 docker 目錄：
   ```bash
   cd docker
   ```

2. 啟動容器：
   ```bash
   docker-compose up -d
   ```

服務啟動後可以通過以下 URL 訪問：
- API 服務：http://localhost:8000
- API 文檔：http://localhost:8000/docs
- Redoc：http://localhost:8000/redoc

## 使用客戶端

### REST API 客戶端

我們提供了一個簡單的 Python 客戶端來訪問 REST API：

```python
from tick_api_client import get_tick_data

# 查詢特定股票的 Tick 資料
stock_id = "2330"  # 台積電
date = "20240508"  # 查詢日期

# 獲取資料（API 會處理價格四捨五入等格式轉換）
df = get_tick_data(stock_id, date, convert_formats=True)

# 查詢含字母的股票代碼也支援
etf_stock_id = "00631L"  # 元大台灣50正2
df_etf = get_tick_data(etf_stock_id, date, convert_formats=True)

# 若成功獲取資料，則保存至 CSV
if not df.empty:
    filename = f"{stock_id}_{date}_tick_data.csv"
    df.to_csv(filename, index=False)
    print(f"已將資料保存至 {filename}")
```

### WebSocket 客戶端

我們提供了兩種 WebSocket 客戶端：

#### 1. 命令行客戶端

```bash
# 基本使用
python websocket_client.py --stock 2330 --date 20240508

# 完整選項
python websocket_client.py --stock 2330 --date 20240508 --server ws://localhost:8000 --save --output-dir ./data
```

參數說明：
- `--stock` 或 `-s`：股票代碼，支援一般股票和含字母的股票代碼，如 ETF（例如：2330, 00631L）
- `--date` 或 `-d`：日期（YYYYMMDD 格式）
- `--server` 或 `-u`：WebSocket 服務器 URL（默認為 ws://localhost:8000）
- `--save` 或 `-o`：是否保存數據到 CSV 文件
- `--output-dir` 或 `-p`：CSV 輸出目錄路徑

#### 2. 圖形界面客戶端

圖形界面客戶端提供了即時價格和成交量圖表：

```bash
python websocket_gui_client.py
```

使用方法：
1. 輸入股票代碼（如 2330 或 00631L）
2. 輸入日期（如 20240508）
3. 點擊「連接」按鈕開始接收數據
4. 數據接收完成後，可以點擊「保存數據」將數據保存為 CSV 文件

## REST API 端點

### 獲取特定日期的 Tick 資料

```
GET /api/v1/tick-data/{stock_id}/date/{date}?convert_formats=true
```

**參數：**
- `stock_id`: 股票代碼（如 2330）
- `date`: 日期（YYYY-MM-DD, YYYY/MM/DD, 或 YYYYMMDD）
- `convert_formats`: 是否轉換格式（默認 true）

**示例：**
```
http://localhost:8000/api/v1/tick-data/2330/date/20240508?convert_formats=true
```

### 獲取日期範圍內的 Tick 資料

```
GET /api/v1/tick-data/{stock_id}/range/{start_date}/{end_date}?convert_formats=true
```

**參數：**
- `stock_id`: 股票代碼
- `start_date`: 開始日期
- `end_date`: 結束日期
- `convert_formats`: 是否轉換格式

**示例：**
```
http://localhost:8000/api/v1/tick-data/2330/range/20240501/20240508?convert_formats=true
```

### 價格四捨五入

```
GET /api/v1/tick-data/price/round/{price}
```

**參數：**
- `price`: 要四捨五入的價格

**示例：**
```
http://localhost:8000/api/v1/tick-data/price/round/123.45
```

## WebSocket 端點

### Tick 資料訂閱

```
WebSocket: /ws/tick/{stock_id}/{date}
```

**參數：**
- `stock_id`: 股票代碼（例如：2330 或 00631L）
- `date`: 日期（YYYYMMDD 格式）

**連接示例：**
```
ws://localhost:8000/ws/tick/2330/20240508
```

連接後，服務器會以每毫秒一條記錄的速率發送 Tick 資料。

### 訂閱流程

1. **連接確認**：連接建立後，服務器發送總記錄數信息。
2. **資料流**：服務器開始發送 Tick 資料，每條包含股票資訊和進度信息。
3. **完成通知**：所有資料發送完畢後，服務器發送一條完成消息，包含統計信息。

## 心跳機制

維持長連接的心跳機制：

```
WebSocket: /ws/heartbeat
```

連接此端點後，服務器會每 30 秒（可配置）發送一條心跳消息。

## 價格四捨五入規則

台灣證券交易所的價格單位規則：

| 價格範圍 (NT$) | 價格單位 |
|---------------|----------|
| 0 - 10        | 0.01     |
| 10 - 50       | 0.05     |
| 50 - 100      | 0.1      |
| 100 - 500     | 0.5      |
| 500 - 1000    | 1.0      |
| 1000+         | 5.0      |

所有價格值將依據這些規則自動四捨五入。

## 時間和日期格式轉換

服務提供自動轉換日期和時間格式：

### 日期轉換
- 原始格式：`20230426`（YYYYMMDD）
- 轉換格式：`2023-04-26`（YYYY-MM-DD）

### 時間轉換
- 原始格式：`93000123`（HHMMSS + 微秒）
- 轉換格式：`09:30:00.123000`（HH:MM:SS.ffffff）

## 常見問題解答

1. **Q: 如何處理含字母的股票代碼（如 ETF）？**  
   A: 我們的 API 已經支援含字母的股票代碼，如「00631L」。

2. **Q: WebSocket 連接中斷後該怎麼辦？**  
   A: 客戶端可以實現重連機制。WebSocket GUI 客戶端會自動處理連接錯誤。

3. **Q: 資料量太大會有效能問題嗎？**  
   A: 對於大量數據，WebSocket 客戶端可能需要足夠的記憶體。可以考慮使用流式處理或分批下載。

4. **Q: 如何知道 WebSocket 傳輸進度？**  
   A: 每條資料中的 `_meta` 欄位包含進度信息，包括當前記錄編號、總記錄數和進度百分比。

5. **Q: 我可以同時獲取多支股票的數據嗎？**  
   A: 目前需要為每支股票建立單獨的連接。未來版本可能支援訂閱多支股票。