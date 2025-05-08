import requests
import pandas as pd
import os
from datetime import datetime, timedelta

def get_tick_data_by_range(stock_id, start_date, end_date, convert_formats=True, api_base_url="http://localhost:8000/api/v1"):
    """
    獲取特定股票在日期範圍內的 Tick 資料
    
    參數:
        stock_id: 股票代碼 (如 '2330')
        start_date: 開始日期 (格式: 'YYYY-MM-DD', 'YYYY/MM/DD' 或 'YYYYMMDD')
        end_date: 結束日期 (格式同上)
        convert_formats: 是否讓 API 轉換資料格式（日期、時間、價格）
        api_base_url: API 基礎 URL
        
    返回:
        包含 Tick 資料的 DataFrame，若失敗則返回空 DataFrame
    """
    # 格式化股票代碼
    stock_id = str(stock_id).strip()
    
    # 構建 API 請求 URL
    url = f"{api_base_url}/tick-data/{stock_id}/range/{start_date}/{end_date}"
    
    # 設置請求參數
    params = {
        'convert_formats': convert_formats
    }
    
    # 顯示請求信息
    print(f"正在查詢 {stock_id} 在 {start_date} 至 {end_date} 的 tick 資料...")
    print(f"請求 URL: {url}")
    print(f"請求參數: {params}")
    
    try:
        # 發送請求
        start_time = datetime.now()
        response = requests.get(url, params=params)
        end_time = datetime.now()
        
        # 計算請求時間
        request_time = (end_time - start_time).total_seconds()
        print(f"請求耗時: {request_time:.2f} 秒")
        
        # 檢查狀態碼
        if response.status_code == 200:
            # 解析回應 JSON
            result = response.json()
            
            # 檢查是否有資料
            data_count = result.get('count', 0)
            if data_count > 0:
                print(f"成功獲取 {data_count} 筆資料!")
                
                # 轉換為 DataFrame
                df = pd.DataFrame(result['data'])
                return df
            else:
                print(f"沒有找到 {stock_id} 在 {start_date} 至 {end_date} 的 tick 資料")
                return pd.DataFrame()
        else:
            print(f"API 請求失敗，狀態碼: {response.status_code}")
            print(f"錯誤詳情: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        print(f"請求發生錯誤: {e}")
        return pd.DataFrame()

def save_to_csv(df, filename):
    """將 DataFrame 保存為 CSV 檔案"""
    if df.empty:
        print("沒有資料可供保存")
        return False
    
    df.to_csv(filename, index=False)
    print(f"已將 {len(df)} 筆資料保存至 {filename}")
    return True

def analyze_date_range_data(df):
    """
    分析日期範圍內的 tick 資料
    
    參數:
        df: 包含 tick 資料的 DataFrame
        
    返回:
        分析結果的字典
    """
    if df.empty:
        return {"error": "沒有資料可供分析"}
    
    analysis = {}
    
    # 基本統計
    analysis["資料筆數"] = len(df)
    
    # 分析日期分佈
    if 'display_date' in df.columns:
        date_counts = df['display_date'].value_counts().sort_index()
        analysis["每日資料筆數"] = date_counts.to_dict()
        analysis["日期範圍"] = f"{date_counts.index.min()} 至 {date_counts.index.max()}"
    
    # 分析價格 (如果有 trade_price 欄位)
    if 'trade_price' in df.columns:
        price_stats = df['trade_price'].describe()
        analysis["價格統計"] = {
            "最高價": price_stats['max'],
            "最低價": price_stats['min'],
            "平均價": price_stats['mean'],
            "中位價": price_stats['50%']
        }
        
        # 如果日期欄位也存在，計算每日價格
        if 'display_date' in df.columns:
            daily_prices = df.groupby('display_date')['trade_price'].agg(['min', 'max', 'mean'])
            analysis["每日價格"] = {
                date: {
                    "最低": row['min'],
                    "最高": row['max'],
                    "平均": row['mean']
                } for date, row in daily_prices.iterrows()
            }
    
    # 分析交易量 (如果有 trade_volume 欄位)
    if 'trade_volume' in df.columns:
        volume_stats = df['trade_volume'].describe()
        analysis["交易量統計"] = {
            "總成交量": df['trade_volume'].sum(),
            "最大單筆成交量": volume_stats['max'],
            "平均成交量": volume_stats['mean']
        }
        
        # 如果日期欄位也存在，計算每日交易量
        if 'display_date' in df.columns:
            daily_volumes = df.groupby('display_date')['trade_volume'].sum()
            analysis["每日交易量"] = daily_volumes.to_dict()
    
    return analysis

# 主程式
if __name__ == "__main__":
    # 設定查詢參數
    stock_id = "2330"  # 台積電
    
    # 設定日期範圍（以最近開始的 3 天為例）
    end_date = "20230426"  # 結束日期
    
    # 計算開始日期（結束日期往前 2 天）
    # 實際使用時，您可以直接指定開始日期
    end_date_obj = datetime.strptime(end_date, "%Y%m%d")
    start_date_obj = end_date_obj - timedelta(days=2)
    start_date = start_date_obj.strftime("%Y%m%d")
    
    print(f"查詢日期範圍: {start_date} 至 {end_date}")
    
    # 獲取資料
    df = get_tick_data_by_range(stock_id, start_date, end_date, convert_formats=True)
    
    # 若成功獲取資料，則進行分析和保存
    if not df.empty:
        # 顯示資料欄位
        print("\n資料欄位:")
        print(df.columns.tolist())
        
        # 顯示前 5 筆資料
        print("\n資料預覽 (前 5 筆):")
        print(df.head())
        
        # 保存資料
        filename = f"{stock_id}_{start_date}_to_{end_date}_tick_data.csv"
        save_to_csv(df, filename)
        
        # 分析資料
        analysis = analyze_date_range_data(df)
        print("\n資料分析結果:")
        for key, value in analysis.items():
            print(f"{key}:")
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, dict):
                        print(f"  {k}:")
                        for subk, subv in v.items():
                            print(f"    {subk}: {subv}")
                    else:
                        print(f"  {k}: {v}")
            else:
                print(f"  {value}")