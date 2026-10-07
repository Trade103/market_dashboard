import datetime
import json
import os
import yfinance as yf


def run_ingestion():
    tickers = ["^IXIC", "^GSPC", "^RUT", "^VIX", "^TNX"]
    summary = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S EST"),
        "tickers": {},
    }

    for symbol in tickers:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="60d")
            if not hist.empty and len(hist) >= 2:
                spot = float(hist["Close"].iloc[-1])
                prior = float(hist["Close"].iloc[-2])

                # Safe rolling average calculation
                sma_50_series = hist["Close"].rolling(window=50).mean()
                sma_50 = (
                    float(sma_50_series.iloc[-1])
                    if not sma_50_series.dropna().empty
                    else spot
                )

                volume_val = (
                    int(hist["Volume"].iloc[-1])
                    if "Volume" in hist.columns and not hist["Volume"].empty
                    else 0
                )

                summary["tickers"][symbol] = {
                    "close": round(spot, 2),
                    "change_pct": round(((spot - prior) / prior) * 100, 2),
                    "sma_50_diff_pct": round(
                        ((spot - sma_50) / sma_50) * 100, 2
                    ),
                    "volume": volume_val,
                }
        except Exception as e:
            print(f"Warning: Failed to fetch {symbol}: {e}")

    # Determine absolute project root path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")

    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "market_snapshot.json")

    with open(file_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Successfully wrote market snapshot to {file_path}")


if __name__ == "__main__":
    run_ingestion()
