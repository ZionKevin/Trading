# -*- coding: utf-8 -*-
"""Smoke test: fetch crypto + commodity từ yfinance."""
import yfinance as yf
import pandas as pd
import ta

print("=" * 60)
print("TEST 1: yfinance BTC-USD (Bitcoin), 50 nến 1h")
print("=" * 60)
btc = yf.Ticker("BTC-USD")
hist = btc.history(period="7d", interval="1h")
if hist.empty:
    print("[FAIL] yfinance trả empty cho BTC-USD")
else:
    df = hist.tail(50).copy()
    print(f"Số nến: {len(df)}")
    print(f"Nến mới nhất: {df.index[-1]}")
    print(f"Close cuối: ${df['Close'].iloc[-1]:,.2f}")
    print(f"Range 50 nến: ${df['Low'].min():,.2f} → ${df['High'].max():,.2f}")

    # Quick check indicator
    rsi = ta.momentum.rsi(df["Close"], window=14).iloc[-1]
    ema20 = ta.trend.ema_indicator(df["Close"], window=20).iloc[-1]
    print(f"RSI(14): {rsi:.2f}")
    print(f"EMA(20): ${ema20:,.2f}")

print()
print("=" * 60)
print("TEST 2: ETH-USD (Ethereum), 20 nến 1h")
print("=" * 60)
eth = yf.Ticker("ETH-USD")
hist = eth.history(period="3d", interval="1h")
if hist.empty:
    print("[FAIL] yfinance trả empty cho ETH-USD")
else:
    print(f"Số nến: {len(hist)}")
    print(f"Close cuối: ${hist['Close'].iloc[-1]:,.2f}")

print()
print("=" * 60)
print("TEST 3: GC=F (Gold futures), daily")
print("=" * 60)
gold = yf.Ticker("GC=F")
hist = gold.history(period="30d", interval="1d")
if hist.empty:
    print("[FAIL] yfinance trả empty cho GC=F")
else:
    print(f"Số nến: {len(hist)}")
    print(f"Close cuối: ${hist['Close'].iloc[-1]:,.2f}")

print()
print("=" * 60)
print("TEST 4: SI=F (Silver futures), daily")
print("=" * 60)
silver = yf.Ticker("SI=F")
hist = silver.history(period="30d", interval="1d")
if hist.empty:
    print("[FAIL] yfinance trả empty cho SI=F")
else:
    print(f"Số nến: {len(hist)}")
    print(f"Close cuối: ${hist['Close'].iloc[-1]:,.2f}")

print()
print("=" * 60)
print("TEST 5: CL=F (Crude Oil futures), daily")
print("=" * 60)
oil = yf.Ticker("CL=F")
hist = oil.history(period="30d", interval="1d")
if hist.empty:
    print("[FAIL] yfinance trả empty cho CL=F")
else:
    print(f"Số nến: {len(hist)}")
    print(f"Close cuối: ${hist['Close'].iloc[-1]:,.2f}")

print()
print("=" * 60)
print("TEST 6: DX-Y.NYB (US Dollar Index), daily")
print("=" * 60)
dxy = yf.Ticker("DX-Y.NYB")
hist = dxy.history(period="60d", interval="1d")
if hist.empty:
    print("[FAIL] yfinance trả empty cho DX-Y.NYB")
else:
    print(f"Số nến: {len(hist)}")
    print(f"Close cuối: {hist['Close'].iloc[-1]:.3f}")

print()
print("=== ALL TESTS DONE ===")
