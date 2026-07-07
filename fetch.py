# -*- coding: utf-8 -*-
"""Fetch OHLCV data từ TradingView (realtime, không delay)."""

# Bước 1: import tvDatafeed (chỉ ImportError xảy ra ở đây).
try:
    from tvDatafeed import TvDatafeed, Interval
    TV_AVAILABLE = True
except ImportError:
    TV_AVAILABLE = False
    Interval = None

# Bước 2: khởi tạo TV session RIÊNG. TvDatafeed() mở kết nối mạng/websocket
# nên có thể ném ConnectionError/RuntimeError... — KHÔNG để lỗi đó làm crash
# import (nếu không cả bot chết lúc khởi động systemd). Fail → fallback yfinance.
_tv = None
if TV_AVAILABLE:
    try:
        _tv = TvDatafeed()  # No login = limited but works for major pairs
    except Exception as e:
        print(f"[WARN] TvDatafeed init fail: {e} — chuyển sang yfinance fallback")
        TV_AVAILABLE = False

# Fallback yfinance nếu tvDatafeed fail
import yfinance as yf
import threading

# Lock bảo vệ _tv: TvDatafeed dùng 1 websocket chung, KHÔNG thread-safe. Cho phép
# gọi fetch_symbol từ nhiều asyncio.to_thread (alert loop + command) mà không đụng nhau.
_tv_lock = threading.Lock()

# Symbol mapping TradingView format: (symbol, exchange)
TV_SYMBOLS = {
    "BTC":   ("BTCUSD",  "COINBASE"),
    "ETH":   ("ETHUSD",  "COINBASE"),
    "XAU":   ("XAUUSD",  "OANDA"),   # Real-time Gold spot
    "XAG":   ("XAGUSD",  "OANDA"),
    "USOIL": ("USOIL",   "TVC"),
    "DXY":   ("DXY",     "TVC"),
}

# Fallback yfinance symbols
YF_SYMBOLS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "XAU": "GC=F",
    "XAG": "SI=F",
    "USOIL": "CL=F",
    "DXY": "DX-Y.NYB",
}

# Map timeframe to TV interval
if TV_AVAILABLE:
    TV_INTERVALS = {
        "1m":  Interval.in_1_minute,
        "5m":  Interval.in_5_minute,
        "15m": Interval.in_15_minute,
        "1h":  Interval.in_1_hour,
        "4h":  Interval.in_4_hour,
        "1d":  Interval.in_daily,
    }
else:
    TV_INTERVALS = {}


def fetch_symbol(symbol, timeframe="5m", days=7):
    """Fetch OHLCV — ưu tiên TradingView (realtime), fallback yfinance.

    Args:
        symbol: "BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"
        timeframe: "1m", "5m", "15m", "1h", "1d"
        days: số ngày (chỉ dùng cho yfinance fallback)

    Returns:
        pd.DataFrame: ['Open','High','Low','Close','Volume'], index=datetime
    """
    if symbol not in TV_SYMBOLS:
        raise ValueError(f"Symbol {symbol} không hỗ trợ. Dùng: {list(TV_SYMBOLS.keys())}")

    # Try TradingView first (realtime)
    if TV_AVAILABLE:
        try:
            tv_sym, tv_exch = TV_SYMBOLS[symbol]
            tv_interval = TV_INTERVALS.get(timeframe, Interval.in_5_minute)
            # n_bars theo timeframe (trước đây *200 luôn → fetch dư ~20 năm daily).
            bars_per_day = {"1m": 1440, "5m": 288, "15m": 96, "1h": 24, "4h": 6, "1d": 1}.get(timeframe, 288)
            n_bars = min(days * bars_per_day, 5000)
            n_bars = max(n_bars, 120)  # đủ nến cho indicators (MA89 cần ≥89)
            with _tv_lock:  # serialize truy cập websocket dùng chung
                df = _tv.get_hist(symbol=tv_sym, exchange=tv_exch,
                                  interval=tv_interval, n_bars=n_bars)
            if df is not None and not df.empty:
                # Rename columns to match yfinance format
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                })
                return df
        except Exception as e:
            print(f"[WARN] TradingView fetch fail {symbol}: {e}, fallback yfinance")

    # Fallback yfinance — lưu ý XAU→GC=F / XAG→SI=F là futures có thể delay 15-30 min
    if symbol in ("XAU", "XAG"):
        print(f"[WARN] {symbol} fallback yfinance ({YF_SYMBOLS[symbol]}) — giá futures có thể delay 15-30 min")
    ticker = yf.Ticker(YF_SYMBOLS[symbol])
    # yfinance không có interval 4h → fetch 1h rồi resample
    yf_interval = "1h" if timeframe == "4h" else timeframe
    hist = ticker.history(period=f"{days}d", interval=yf_interval)
    if hist.empty:
        raise ValueError(f"Không fetch được {symbol} {timeframe} (cả TV và yfinance fail)")
    if timeframe == "4h":
        hist = hist.resample("4h").agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()
    return hist


def load_multiple(symbols_list, timeframe="1d", days=30):
    """Load nhiều symbol cùng lúc."""
    data = {}
    for sym in symbols_list:
        try:
            data[sym] = fetch_symbol(sym, timeframe, days)
        except Exception as e:
            print(f"[WARN] Lỗi fetch {sym}: {e}")
    return data


def load_all_symbols(timeframe="1d", days=30):
    """Load tất cả 6 symbol."""
    return load_multiple(list(TV_SYMBOLS.keys()), timeframe, days)


if __name__ == "__main__":
    print(f"TradingView available: {TV_AVAILABLE}")
    print("Fetch XAU 5m (realtime)...")
    xau = fetch_symbol("XAU", "5m", 1)
    print(f"  → {len(xau)} nến, cuối: {xau.index[-1]}, close: ${xau['Close'].iloc[-1]:,.2f}")
