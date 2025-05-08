import requests
import pandas as pd
import os

def get_tick_data(stock_id, date, convert_formats=True, api_base_url="http://localhost:8000/api/v1"):
    """
    獲取特定股票在特定日期的 Tick 資料
    
    參數:
        stock_id: 股票代碼 (如 '2330')
        date: 日期 (格式: 'YYYY-MM-DD', 'YYYY/MM/DD' 或 'YYYYMMDD')
        convert_formats: 是否讓 API 轉換資料格式（日期、時間、價格）
        api_base_url: API 基礎 URL
        
    返回:
        包含 Tick 資料的 DataFrame，若失敗則返回空 DataFrame
    """
    # 格式化股票代碼
    stock_id = str(stock_id).strip()
    
    # 構建 API 請求 URL
    url = f"{api_base_url}/tick-data/{stock_id}/date/{date}"
    
    # 設置請求參數
    params = {
        'convert_formats': convert_formats
    }
    
    # 顯示請求信息
    print(f"正在查詢 {stock_id} 在 {date} 的 tick 資料...")
    print(f"請求 URL: {url}")
    
    try:
        # 發送請求
        response = requests.get(url, params=params)
        
        # 檢查狀態碼
        if response.status_code == 200:
            result = response.json()
            print(response.text)
            # 檢查是否有資料
            data_count = result.get('count', 0)
            if data_count > 0:
                print(f"成功獲取 {data_count} 筆資料!")
                
                # 轉換為 DataFrame（資料已經由 API 處理好了）
                df = pd.DataFrame(result['data'])
                return df
            else:
                print(f"沒有找到 {stock_id} 在 {date} 的 tick 資料")
                return pd.DataFrame()
        else:
            print(f"API 請求失敗: {response.status_code}")
            print(f"錯誤訊息: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        print(f"請求過程中發生錯誤: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # 設定查詢參數
    stock_id = "03011P"  # 台積電
    date = "20241213"  # 查詢日期
    
    # 獲取資料（API 會處理價格四捨五入等格式轉換）
    df = get_tick_data(stock_id, date, convert_formats=True)
    
    # 若成功獲取資料，則保存至 CSV
    if not df.empty:
        # 顯示資料欄位
        print("\n資料欄位:")
        print(df.columns.tolist())
        
        # 顯示前 5 筆資料
        print("\n資料預覽 (前 5 筆):")
        print(df.head())
        
        # 保存資料
        filename = f"{stock_id}_{date}_tick_data.csv"
        df.to_csv(filename, index=False)
        print(f"已將資料保存至 {filename}")