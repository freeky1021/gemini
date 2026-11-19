import pandas as pd
import numpy as np
import sys

# ==========================================
# 1. 設定檔案路徑
# ==========================================
input_file = "data.csv"          # 👈 請改成你實際的 1分K 檔名
output_day_file = "TX_Daily_Day.csv"     # 輸出的純日盤日K
output_night_file = "TX_Daily_Night.csv" # 輸出的純夜盤日K (以開盤日 15:00 為準)

print(f"🚀 開始讀取 1分K 資料檔: {input_file} ...")

try:
    # index_col=0 自動將無欄位名的第一欄（時間）設為 Index
    df = pd.read_csv(input_file, index_col=0, parse_dates=True)
    print("📥 原始資料欄位:", df.columns.tolist())
except FileNotFoundError:
    print(f"❌ 錯誤：找不到檔案 '{input_file}'，請確認檔名與路徑是否正確！")
    sys.exit()

# ==========================================
# 2. 時間與欄位名稱正規化
# ==========================================
df.index = pd.to_datetime(df.index)
df.sort_index(inplace=True)

# 統一欄位首字母大寫 (open -> Open, volume -> Volume)
df.rename(columns={
    col: col.capitalize() for col in df.columns if col.lower() in ['open', 'high', 'low', 'close', 'volume']
}, inplace=True)

# ==========================================
# 3. 區分日盤與夜盤，並精準綁定夜盤歸屬日期
# ==========================================
print("⏳ 正在切割日夜盤並綁定夜盤開盤日期...")

# 日盤：08:45 至 13:46
is_day_session = (df.index.hour > 8) & (df.index.hour < 13) | \
                 ((df.index.hour == 8) & (df.index.minute >= 45)) | \
                 ((df.index.hour == 13) & (df.index.minute <= 46))

# 夜盤：15:00 至 次日 05:00
is_night_session = (df.index.hour >= 15) | \
                   (df.index.hour < 5) | \
                   ((df.index.hour == 5) & (df.index.minute == 0))
                   
df_day_raw = df[is_day_session].copy()
df_night_raw = df[is_night_session].copy()

# --- 日盤日期歸屬：直接取當天日期 (08:45~13:46) ---
df_day_raw['TradeDate'] = df_day_raw.index.date

# --- 夜盤日期歸屬：精準綁定開盤當天 (7/24 15:00 ~ 7/25 05:00 歸為 7/24) ---
# 邏輯：
# 15:00~23:59 (如 7/24 15:01) -> hour < 5 為 False (0天) -> 日期維持 7/24
# 00:00~05:00 (如 7/25 04:59) -> hour < 5 為 True (1天)  -> 7/25 減 1 天變 7/24
shift_days = pd.to_timedelta((df_night_raw.index.hour <= 5).astype(int), unit='D')
df_night_raw['TradeDate'] = df_night_raw.index.date - shift_days

# ==========================================
# 4. 合成 K 線 (Resample / GroupBy)
# ==========================================
def aggregate_kline(df_session):
    if df_session.empty:
        return pd.DataFrame()
    
    daily = df_session.groupby('TradeDate').agg({
        'Open': 'first',     # 該夜盤開盤第一根 (15:01) 的開盤價
        'High': 'max',       # 跨夜 (15:00~次日05:00) 綜合最高價
        'Low': 'min',        # 跨夜 (15:00~次日05:00) 綜合最低價
        'Close': 'last',     # 該夜盤收盤最後一根 (次日05:00) 的收盤價
        'Volume': 'sum'      # 跨夜總成交量
    }).dropna()
    
    daily.index.name = 'Date'
    daily.reset_index(inplace=True)
    daily['Date'] = pd.to_datetime(daily['Date']).dt.strftime('%Y-%m-%d')
    return daily

print("📊 合成【日盤】日K...")
daily_day = aggregate_kline(df_day_raw)

print("📊 合成【夜盤】日K (按開盤日歸戶)...")
daily_night = aggregate_kline(df_night_raw)

# ==========================================
# 5. 輸出檔
# ==========================================
daily_day.to_csv(output_day_file, index=False)
daily_night.to_csv(output_night_file, index=False)

print("\n" + "="*55)
print("🎉 轉換成功！")
print(f"☀️  日盤日K檔: {output_day_file} (共 {len(daily_day)} 筆)")
print(f"🌙 夜盤日K檔: {output_night_file} (共 {len(daily_night)} 筆)")
print("="*55)

print("\n【🌙 夜盤 (TX_Daily_Night.csv) 範例預覽】:")
print(daily_night.head(3))