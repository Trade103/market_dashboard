import datetime
import json
import os
import requests
import yfinance as yf

def run_ingestion():
    tickers = {
        "^IXIC": "Nasdaq",
        "^GSPC": "S&P 500",
        "^RUT": "Russell 2000",
        "^VIX": "VIX",
        "^TNX": "TNX"
    }
    
    summary = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S EST"),
        "tickers": {}
    }
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    for symbol, name in tickers.items():
        try:
            t = yf.Ticker(symbol, session=session)
            hist = t.history(period="60d")
            
            if not hist.empty and len(hist) >= 2:
                spot = float(hist["Close"].iloc[-1])
                prior = float(hist["Close"].iloc[-2])
                
                sma_50_series = hist["Close"].rolling(window=50).mean()
                sma_50 = float(sma_50_series.iloc[-1]) if not sma_50_series.dropna().empty else spot
                
                vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns and not hist["Volume"].dropna().empty else 0
                
                summary["tickers"][symbol] = {
                    "name": name,
                    "close": round(spot, 2),
                    "change_pct": round(((spot - prior) / prior) * 100, 2),
                    "sma_50_diff_pct": round(((spot - sma_50) / sma_50) * 100, 2),
                    "volume": vol
                }
            else:
                print(f"Warning: Empty history for {symbol}")
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")
    
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "market_snapshot.json")
    
    with open(file_path, "w") as f:
        json.dump(summary, f, indent=2)
        
    print(f"Successfully saved snapshot to {file_path}")

if __name__ == "__main__":
    run_ingestion()
