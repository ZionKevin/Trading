# -*- coding: utf-8 -*-
"""Fetch OHLCV data từ yfinance cho 6 symbol."""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Symbol mapping: name -> yfinance ticker
SYMBOLS = {
    "BTC": "BTC-USD",      # Crypto: support 1h + daily
    "ETH": "ETH-USD",
    "XAU": "GC=F",         # Commodity: daily chủ yếu
    "XAG": "SI=F",
    "USOIL": "CL=F",
    "DXY": "DX-Y.NYB",
}

def fetch_symbol(symbol, timeframe="1d", days=30):
    """Fetch OHLCV từ yfinance cho 1 symbol.

    Args:
        symbol: "BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"
        timeframe: "1m", "5m", "15m", "1h", "1d"
        days: lấy N ngày gần nhất

    Returns:
        pd.DataFrame: columns ['Open','High','Low','Close','Volume'], index=datetime
    """
    if symbol not in SYMBOLS:
        raise ValueError(f"Symbol {symbol} không hỗ trợ. Dùng: {list(SYMBOLS.keys())}")

    ticker_str = SYMBOLS[symbol]
    ticker = yf.Ticker(ticker_str)

    hist = ticker.history(period=f"{days}d", interval=timeframe)
    if hist.empty:
        raise ValueError(f"Không fetch được {symbol} ({ticker_str}) {timeframe}")

    return hist


def load_multiple(symbols_list, timeframe="1d", days=30):
    """Load nhiều symbol cùng lúc.

    Args:
        symbols_list: ["BTC", "ETH", "XAU", ...]
        timeframe: "1h", "1d", ...
        days: số ngày

    Returns:
        dict: {symbol -> df}
    """
    data = {}
    for sym in symbols_list:
        try:
            data[sym] = fetch_symbol(sym, timeframe, days)
        except Exception as e:
            print(f"[WARN] Lỗi fetch {sym}: {e}")
    return data


def load_all_symbols(timeframe="1d", days=30):
    """Load tất cả 6 symbol."""
    return load_multiple(list(SYMBOLS.keys()), timeframe, days)


if __name__ == "__main__":
    # Test
    print("Fetch BTC 1h (7 ngày)...")
    btc = fetch_symbol("BTC", "1h", 7)
    print(f"  → {len(btc)} nến, cuối: {btc.index[-1]}, close: ${btc['Close'].iloc[-1]:,.2f}")

    print("Fetch XAU daily (30 ngày)...")
    xau = fetch_symbol("XAU", "1d", 30)
    print(f"  → {len(xau)} nến, cuối: {xau.index[-1]}, close: ${xau['Close'].iloc[-1]:,.2f}")
