import datetime
import json
import os
import pandas as pd
import requests
import yfinance as yf

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def run_ingestion():
    tickers = ["^IXIC", "^GSPC", "^RUT", "^VIX", "^TNX"]
    summary = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S EST"),
        "tickers": {},
    }

    for symbol in tickers:
        t = yf.Ticker(symbol)
        hist = t.history(period="60d")
        if not hist.empty:
            spot = float(hist["Close"].iloc[-1])
            prior = float(hist["Close"].iloc[-2])
            sma_50 = float(hist["Close"].rolling(window=50).mean().iloc[-1])

            summary["tickers"][symbol] = {
                "close": spot,
                "change_pct": round(((spot - prior) / prior) * 100, 2),
                "sma_50_diff_pct": round(((spot - sma_50) / sma_50) * 100, 2),
                "volume": int(hist["Volume"].iloc[-1]),
            }

    os.makedirs("data", exist_ok=True)
    with open("data/market_snapshot.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Successfully wrote snapshot at {summary['timestamp']}")


if __name__ == "__main__":
    run_ingestion()
