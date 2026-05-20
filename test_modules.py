# -*- coding: utf-8 -*-
"""Test fetch + indicators modules."""
from fetch import fetch_symbol
from indicators import IndicatorSet

print("=" * 70)
print("TEST: Fetch BTC 1h + Calculate Indicators")
print("=" * 70)

# Fetch
print("\n1. Fetch BTC 1h (50 nến)...")
df = fetch_symbol("BTC", "1h", days=7)
print(f"   OK: {len(df)} nến, cuối: {df.index[-1]}")

# Calculate
print("\n2. Calculate all indicators...")
ind = IndicatorSet(df).calculate_all()
print("   OK: Indicator set ready")

# Display
print("\n3. Latest values:")
latest = ind.all_latest()
for name, val in sorted(latest.items())[:10]:  # Show first 10
    if isinstance(val, float):
        print(f"   {name}: {val:.4f}")

print("\n4. Trend check:")
print(f"   EMA20: ${latest['ema20']:,.2f}")
print(f"   EMA50: ${latest['ema50']:,.2f}")
print(f"   EMA200: ${latest['ema200']:,.2f}")
print(f"   RSI: {latest['rsi']:.2f}")
print(f"   MACD Hist: {latest['macd_hist']:.6f}")
print(f"   SuperTrend: {latest['supertrend']:.2f}")
print(f"   SuperTrend Trend: {'UP' if latest['supertrend_trend'] == 1 else 'DOWN'}")

print("\n=== TEST PASSED ===")
