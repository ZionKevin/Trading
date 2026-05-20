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


def detect_trendline_breakout(df, lookback=20):
    """Detect trendline break: higher lows (uptrend) hay lower highs (downtrend).

    Returns:
        dict: {'trend': 'UP'/'DOWN', 'trendline_price': float, 'broken': bool}
    """
    recent = df.tail(lookback)
    lows = recent['Low'].values
    highs = recent['High'].values

    # Detect higher lows (uptrend trendline)
    hl_count = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
    # Detect lower highs (downtrend trendline)
    lh_count = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])

    if hl_count > lh_count:
        # Uptrend: check if break of support line
        support_line = min(lows[-3:])  # Last 3 lows min
        current_low = df['Low'].iloc[-1]
        broken = current_low < support_line
        return {'trend': 'UP', 'trendline_price': support_line, 'broken': broken}
    else:
        # Downtrend: check if break of resistance line
        resistance_line = max(highs[-3:])  # Last 3 highs max
        current_high = df['High'].iloc[-1]
        broken = current_high > resistance_line
        return {'trend': 'DOWN', 'trendline_price': resistance_line, 'broken': broken}


def find_scalp_entry(df, symbol="XAU", h1_df=None):
    """Tìm entry point scalp dựa vào bounce + breakout + trendline + trend confirm.

    Args:
        df: M5/M15 dataframe
        symbol: symbol name
        h1_df: H1 dataframe (optional) để check macro trend

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

    # Pivot points
    high = df['High'].iloc[-1]
    low = df['Low'].iloc[-1]
    close = df['Close'].iloc[-1]

    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)

    # Detect support/resistance
    sr = detect_support_resistance(df, lookback=15)

    # Detect trendline
    trendline_info = detect_trendline_breakout(df, lookback=20)

    # Check H1 trend confirmation
    h1_trend = None
    if h1_df is not None and len(h1_df) > 0:
        h1_ind = IndicatorSet(h1_df).calculate_all()
        h1_rsi = h1_ind.latest('rsi')
        h1_trend = "UP" if h1_rsi < 50 else "DOWN" if h1_rsi > 50 else "NEUTRAL"

    # Entry logic
    entry = None
    signal_type = None
    confirmation = None

    touch_threshold = 2  # within 2 pips

    # ===== BUY SIGNALS =====
    # 1. Bounce from support/MA89/S1
    if current_price <= ma89 + touch_threshold and current_price >= ma89 - touch_threshold:
        if current_price > ma89 - touch_threshold:
            entry = current_price
            signal_type = "BUY_MA89_BOUNCE"

    if not entry and sr['supports'] and current_price <= sr['supports'][-1] + touch_threshold:
        if current_price > sr['supports'][-1] - touch_threshold:
            entry = current_price
            signal_type = "BUY_SUPPORT_BOUNCE"

    if not entry and abs(current_price - s1) <= touch_threshold:
        if current_price > s1 - touch_threshold:
            entry = current_price
            signal_type = "BUY_PIVOT_S1_BOUNCE"

    # 2. Breakout signals
    if not entry and trendline_info['trend'] == 'UP' and trendline_info['broken']:
        entry = current_price
        signal_type = "BUY_TRENDLINE_BREAKUP"

    if not entry and sr['supports'] and current_price < sr['supports'][-1] - 3:
        # Strong break below support
        entry = current_price
        signal_type = "BUY_SUPPORT_BREAK"

    # ===== SELL SIGNALS =====
    # 1. Bounce from resistance/R1
    if not entry and sr['resistances'] and current_price >= sr['resistances'][0] - touch_threshold:
        if current_price < sr['resistances'][0] + touch_threshold:
            entry = current_price
            signal_type = "SELL_RESISTANCE_BOUNCE"

    if not entry and abs(current_price - r1) <= touch_threshold:
        if current_price < r1 + touch_threshold:
            entry = current_price
            signal_type = "SELL_PIVOT_R1_BOUNCE"

    # 2. Breakout signals
    if not entry and trendline_info['trend'] == 'DOWN' and trendline_info['broken']:
        entry = current_price
        signal_type = "SELL_TRENDLINE_BREAKDN"

    if not entry and sr['resistances'] and current_price > sr['resistances'][0] + 3:
        # Strong break above resistance
        entry = current_price
        signal_type = "SELL_RESISTANCE_BREAK"

    if not entry:
        return None

    # Tính SL/TP
    if "BUY" in signal_type:
        sl = entry - 6  # 6 pips SL
        tp = entry + 10  # 10 pips TP
    else:  # SELL
        sl = entry + 6
        tp = entry - 10

    # H1 confirmation string
    if h1_trend:
        if "BUY" in signal_type and h1_trend == "UP":
            confirmation = f"✅ H1 {h1_trend} aligned"
        elif "SELL" in signal_type and h1_trend == "DOWN":
            confirmation = f"✅ H1 {h1_trend} aligned"
        else:
            confirmation = f"⚠️ H1 {h1_trend} (check confluence)"

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
        'r1': r1,
        'r2': r2,
        's2': s2,
        'trendline': trendline_info['trendline_price'],
        'trendline_broken': trendline_info['broken'],
        'h1_confirmation': confirmation
    }


def check_m5_scalp():
    """M5 scalp analysis cho XAU."""
    symbols = ["XAU"]
    lines = [f"M5 SCALP SETUP — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df_m5 = fetch_symbol(sym, "5m", 7)
            df_h1 = fetch_symbol(sym, "1h", 5)
            setup = find_scalp_entry(df_m5, sym, df_h1)

            if setup:
                current = df_m5['Close'].iloc[-1]
                direction = "BUY" if "BUY" in setup['signal'] else "SELL"

                # Action text
                if "BOUNCE" in setup['signal']:
                    action = f"Wait for bounce to {setup['entry']:.2f}"
                    level_name = "support" if "BUY" in setup['signal'] else "resistance"
                elif "BREAKOUT" in setup['signal'] or "BREAK" in setup['signal']:
                    action = f"Enter on break above {setup['entry']:.2f}" if "BUY" in setup['signal'] else f"Enter on break below {setup['entry']:.2f}"
                    level_name = "level"
                else:
                    action = f"Enter at {setup['entry']:.2f}"
                    level_name = "entry"

                lines.append(f"{direction} - {sym}")
                lines.append(f"Current: {current:.2f} | {level_name.capitalize()}: {setup['entry']:.2f}")
                lines.append(f"Entry: {setup['entry']:.2f} | SL: {setup['sl']:.2f} | TP: {setup['tp']:.2f}")
                lines.append(f"Action: {action}")
                lines.append(f"Signal: {setup['signal']}")
                if setup['h1_confirmation']:
                    lines.append(f"{setup['h1_confirmation']}")
            else:
                lines.append(f"No M5 setup yet")
        except Exception as e:
            lines.append(f"ERROR: {str(e)[:50]}")

    return "\n".join(lines)


def check_m15_scalp():
    """M15 scalp analysis cho XAU."""
    symbols = ["XAU"]
    lines = [f"M15 SCALP SETUP — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df_m15 = fetch_symbol(sym, "15m", 7)
            df_h1 = fetch_symbol(sym, "1h", 5)
            setup = find_scalp_entry(df_m15, sym, df_h1)

            if setup:
                current = df_m15['Close'].iloc[-1]
                direction = "BUY" if "BUY" in setup['signal'] else "SELL"

                # Action text
                if "BOUNCE" in setup['signal']:
                    action = f"Wait for bounce to {setup['entry']:.2f}"
                    level_name = "support" if "BUY" in setup['signal'] else "resistance"
                elif "BREAKOUT" in setup['signal'] or "BREAK" in setup['signal']:
                    action = f"Enter on break above {setup['entry']:.2f}" if "BUY" in setup['signal'] else f"Enter on break below {setup['entry']:.2f}"
                    level_name = "level"
                else:
                    action = f"Enter at {setup['entry']:.2f}"
                    level_name = "entry"

                lines.append(f"{direction} - {sym}")
                lines.append(f"Current: {current:.2f} | {level_name.capitalize()}: {setup['entry']:.2f}")
                lines.append(f"Entry: {setup['entry']:.2f} | SL: {setup['sl']:.2f} | TP: {setup['tp']:.2f}")
                lines.append(f"Action: {action}")
                lines.append(f"Signal: {setup['signal']}")
                if setup['h1_confirmation']:
                    lines.append(f"{setup['h1_confirmation']}")
            else:
                lines.append(f"No M15 setup yet")
        except Exception as e:
            lines.append(f"ERROR: {str(e)[:50]}")

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
