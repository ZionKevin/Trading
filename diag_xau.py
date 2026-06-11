# -*- coding: utf-8 -*-
"""Dò xem feed XAU nào tvDatafeed (nologin) lấy được giá spot đúng (~4078).
Chạy trên VPS: python3 diag_xau.py
An toàn — KHÔNG đụng Telegram (không gây 409 conflict)."""

try:
    from tvDatafeed import TvDatafeed, Interval
except ImportError as e:
    print("tvDatafeed CHƯA cài:", e)
    raise SystemExit(1)

print("Đang init TvDatafeed (nologin)...")
try:
    tv = TvDatafeed()
except Exception as e:
    print("TvDatafeed() init FAIL:", e)
    raise SystemExit(1)

# Các feed XAU ứng viên (spot, không phải futures)
CANDIDATES = [
    ("XAUUSD", "OANDA"),
    ("XAUUSD", "FX_IDC"),
    ("XAUUSD", "FOREXCOM"),
    ("XAUUSD", "FXCM"),
    ("XAUUSD", "PEPPERSTONE"),
    ("XAUUSD", "ICMARKETS"),
    ("GOLD",   "TVC"),
    ("XAUUSD", "CAPITALCOM"),
    ("XAUUSD", "SAXO"),
    ("XAUUSD", "BLACKBULL"),
]

print(f"\n{'FEED':<24} {'CLOSE':>12}   TIME")
print("-" * 60)
for sym, exch in CANDIDATES:
    label = f"{exch}:{sym}"
    try:
        df = tv.get_hist(symbol=sym, exchange=exch,
                         interval=Interval.in_5_minute, n_bars=2)
        if df is None or df.empty:
            print(f"{label:<24} {'EMPTY':>12}")
        else:
            close = df['close'].iloc[-1]
            t = df.index[-1]
            print(f"{label:<24} {close:>12,.2f}   {t}")
    except Exception as e:
        print(f"{label:<24} {'ERR':>12}   {str(e)[:40]}")

print("\n=> Chọn feed nào CLOSE ≈ 4078 (khớp TradingView spot) để báo lại.")
