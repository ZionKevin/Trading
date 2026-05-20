# -*- coding: utf-8 -*-
"""Scalp setup trên M5/M15 - dùng support/resistance + pivot + MA89."""
from fetch import fetch_symbol
from indicators import IndicatorSet
from datetime import datetime
import numpy as np


def detect_support_resistance(df, lookback=10):
    """Detect support (lows) + resistance (highs) từ recent candles.

    Args:
        df: DataFrame với OHLCV
        lookback: số nến để scan

    Returns:
        dict: {'supports': [prices], 'resistances': [prices]}
    """
    recent = df.tail(lookback)

    # Support = recent lows, Resistance = recent highs
    supports = sorted(recent['Low'].nsmallest(2).values)  # 2 lowest
    resistances = sorted(recent['High'].nlargest(2).values, reverse=True)  # 2 highest

    return {'supports': supports, 'resistances': resistances}


def find_scalp_entry(df, symbol="XAU"):
    """Tìm entry point scalp dựa vào support/resistance + MA89 + pivot.

    Returns:
        dict với entry, SL, TP hoặc None nếu không có setup
    """
    if len(df) < 100:
        return None

    # Tính indicators
    ind = IndicatorSet(df).calculate_all()

    # Lấy current price + levels
    current_price = df['Close'].iloc[-1]
    ma89 = ind.latest('ma89_close')

    # Pivot points (dùng day nhất gần đây làm base)
    high = df['High'].iloc[-1]
    low = df['Low'].iloc[-1]
    close = df['Close'].iloc[-1]

    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high

    # Detect support/resistance
    sr = detect_support_resistance(df, lookback=15)

    # Lấy last 3 candles để check bounce
    last_candles = df.tail(3)
    last_low = last_candles['Low'].min()
    last_high = last_candles['High'].max()

    # Entry logic: price gần support/MA89/S1 = potential bounce
    entry = None
    signal_type = None

    # BUY signal: price chạm support hoặc MA89 hoặc S1
    touch_threshold = 2  # within 2 pips

    if current_price <= ma89 + touch_threshold and current_price >= ma89 - touch_threshold:
        if current_price > ma89 - touch_threshold:  # touching from above = bounce up
            entry = current_price
            signal_type = "BUY_MA89_BOUNCE"

    if sr['supports'] and current_price <= sr['supports'][-1] + touch_threshold:
        if current_price > sr['supports'][-1] - touch_threshold:
            entry = current_price
            signal_type = "BUY_SUPPORT_BOUNCE"

    if abs(current_price - s1) <= touch_threshold:
        if current_price > s1 - touch_threshold:
            entry = current_price
            signal_type = "BUY_PIVOT_S1_BOUNCE"

    # SELL signal: price chạm resistance hoặc R1
    if sr['resistances'] and current_price >= sr['resistances'][0] - touch_threshold:
        if current_price < sr['resistances'][0] + touch_threshold:
            entry = current_price
            signal_type = "SELL_RESISTANCE"

    if abs(current_price - r1) <= touch_threshold:
        if current_price < r1 + touch_threshold:
            entry = current_price
            signal_type = "SELL_PIVOT_R1"

    if not entry:
        return None

    # Tính SL/TP
    if "BUY" in signal_type:
        sl = entry - 6  # 6 pips SL
        tp = entry + 10  # 10 pips TP
    else:  # SELL
        sl = entry + 6
        tp = entry - 10

    return {
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'signal': signal_type,
        'ma89': ma89,
        'support': sr['supports'][-1] if sr['supports'] else None,
        'resistance': sr['resistances'][0] if sr['resistances'] else None,
        'pivot': pivot,
        's1': s1,
        'r1': r1
    }


def check_m5_scalp():
    """M5 scalp analysis cho XAU."""
    symbols = ["XAU"]
    lines = [f"📊 **M5 SCALP SETUP** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "5m", 7)  # 7 days = ~200 M5 candles
            setup = find_scalp_entry(df, sym)

            if setup:
                direction = "🟢 BUY" if "BUY" in setup['signal'] else "🔴 SELL"
                lines.append(f"{direction} **{sym}** @ {setup['entry']:,.2f}")
                lines.append(f"  Entry: {setup['entry']:,.2f} | SL: {setup['sl']:,.2f} | TP: {setup['tp']:,.2f}")
                lines.append(f"  Signal: {setup['signal']}")
                lines.append(f"  MA89: {setup['ma89']:,.2f}")
            else:
                lines.append(f"⏳ **{sym}** — No M5 setup yet")
        except Exception as e:
            lines.append(f"**{sym}:** ERROR - {str(e)[:50]}")

    return "\n".join(lines)


def check_m15_scalp():
    """M15 scalp analysis cho XAU."""
    symbols = ["XAU"]
    lines = [f"📊 **M15 SCALP SETUP** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "15m", 7)
            setup = find_scalp_entry(df, sym)

            if setup:
                direction = "🟢 BUY" if "BUY" in setup['signal'] else "🔴 SELL"
                lines.append(f"{direction} **{sym}** @ {setup['entry']:,.2f}")
                lines.append(f"  Entry: {setup['entry']:,.2f} | SL: {setup['sl']:,.2f} | TP: {setup['tp']:,.2f}")
                lines.append(f"  Signal: {setup['signal']}")
                lines.append(f"  MA89: {setup['ma89']:,.2f}")
            else:
                lines.append(f"⏳ **{sym}** — No M15 setup yet")
        except Exception as e:
            lines.append(f"**{sym}:** ERROR - {str(e)[:50]}")

    return "\n".join(lines)


def check_h1_trend():
    """H1 trend check cho XAU (macro direction)."""
    symbols = ["XAU"]
    lines = [f"📈 **H1 TREND** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "1h", 5)  # 5 days = ~120 H1 candles
            ind = IndicatorSet(df).calculate_all()

            rsi = ind.latest('rsi')
            trend = "UP ↑" if rsi < 50 else "DOWN ↓" if rsi > 50 else "NEUTRAL"

            lines.append(f"**{sym}** - Trend: {trend} | RSI: {rsi:.1f}")
        except Exception as e:
            lines.append(f"**{sym}:** ERROR - {str(e)[:50]}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(check_h1_trend())
    print("\n" + check_m5_scalp())
    print("\n" + check_m15_scalp())
