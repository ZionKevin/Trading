# -*- coding: utf-8 -*-
"""Scalp setup trên M5/M15 - dùng support/resistance + pivot + MA89 + Fibonacci."""
import logging
from fetch import fetch_symbol
from indicators import IndicatorSet
from market_structure import detect_fibonacci_bounce, detect_fibo_rejection_confluence
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


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


def check_volume_strength(df, lookback=20):
    """Check if recent volume is stronger than average.

    Args:
        df: DataFrame với OHLCV
        lookback: days for average

    Returns:
        dict: {'avg_volume': float, 'current_volume': float, 'ratio': float, 'is_strong': bool}
    """
    recent = df.tail(lookback)
    avg_vol = recent['Volume'].mean()
    current_vol = df['Volume'].iloc[-1]

    ratio = current_vol / avg_vol if avg_vol > 0 else 0
    is_strong = ratio > 1.2  # Volume > 120% of average = strong

    return {
        'avg_volume': avg_vol,
        'current_volume': current_vol,
        'ratio': ratio,
        'is_strong': is_strong
    }


def check_consolidation(df, lookback=20):
    """Check if market is consolidating (low ATR = tight range).

    Args:
        df: DataFrame với OHLCV
        lookback: days for ATR average

    Returns:
        dict: {'atr': float, 'atr_avg': float, 'is_consolidating': bool}
    """
    # Simple ATR: average of (High - Low)
    recent = df.tail(lookback)
    current_atr = df['High'].iloc[-1] - df['Low'].iloc[-1]
    avg_atr = recent['High'].sub(recent['Low']).mean()

    # Consolidating if current ATR < 70% of average (tight range)
    is_consolidating = current_atr < (avg_atr * 0.7)

    return {
        'atr': current_atr,
        'atr_avg': avg_atr,
        'is_consolidating': is_consolidating
    }


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

    # Check H1 trend confirmation (RSI > 50 = UP/bullish, RSI < 50 = DOWN/bearish)
    h1_trend = None
    if h1_df is not None and len(h1_df) > 0:
        h1_ind = IndicatorSet(h1_df).calculate_all()
        h1_rsi = h1_ind.latest('rsi')
        h1_trend = "UP" if h1_rsi > 50 else "DOWN" if h1_rsi < 50 else "NEUTRAL"

    # Check consolidation (MUST be before using ATR for SL/TP)
    cons_info = check_consolidation(df, lookback=20)

    # Entry logic
    entry = None
    signal_type = None
    confirmation = None
    fibo_info = None  # Track Fibonacci signals separately

    touch_threshold = 2  # within 2 pips

    # ===== FIBONACCI SIGNALS (Priority - check first) =====
    # Fibonacci retracement bounce detection (38.2% + 61.8%)
    fibo_bounce = detect_fibonacci_bounce(df, lookback=30)
    if fibo_bounce:
        entry = fibo_bounce['entry']
        fibo_info = fibo_bounce

        # Check for rejection candle confluence (high quality setup)
        confluence = detect_fibo_rejection_confluence(df, fibo_bounce, lookback_rejection=3)
        has_confluence = confluence['has_confluence']

        if fibo_bounce['direction'] == 'UP':
            if has_confluence:
                # Fibo + rejection = high quality
                if fibo_bounce['fibo_level'] == 38.2:
                    signal_type = "BUY_FIBO_38_REJECTION"
                else:
                    signal_type = "BUY_FIBO_61_REJECTION"
            else:
                # Fibo solo
                if fibo_bounce['fibo_level'] == 38.2:
                    signal_type = "BUY_FIBO_38_BOUNCE"
                else:
                    signal_type = "BUY_FIBO_61_BOUNCE"
        else:  # DOWN
            if has_confluence:
                # Fibo + rejection = high quality
                if fibo_bounce['fibo_level'] == 38.2:
                    signal_type = "SELL_FIBO_38_REJECTION"
                else:
                    signal_type = "SELL_FIBO_61_REJECTION"
            else:
                # Fibo solo
                if fibo_bounce['fibo_level'] == 38.2:
                    signal_type = "SELL_FIBO_38_BOUNCE"
                else:
                    signal_type = "SELL_FIBO_61_BOUNCE"

        # Store confluence info for learning boost
        fibo_info['confluence'] = confluence

    # ===== BUY SIGNALS =====
    # 1. Bounce from support/MA89/S1
    if not entry and current_price <= ma89 + touch_threshold and current_price >= ma89 - touch_threshold:
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
    # Fibonacci signals: use extension for TP, support/resistance for SL
    # ATR signals: use ATR-based SL/TP (1:2 ratio)
    atr = cons_info['atr']

    if fibo_info:
        # Fibonacci: Use TP2 (161.8%) as primary, TP1/TP3 for partial targets
        tp = fibo_info['tp2']  # Primary TP for learning (161.8%)
        tp1 = fibo_info['tp1']  # Conservative (127.2%)
        tp3 = fibo_info['tp3']  # Aggressive (200%)

        # SL range per-symbol (USD): clamp distance trong khoảng hợp lý cho scalp
        # XAU 10-15$ ≈ 100-150 pips; BTC 200-500$; ETH 30-70$; etc.
        SL_RANGE_USD = {
            'XAU': (10, 15),
            'BTC': (200, 500),
            'ETH': (30, 70),
            'XAG': (0.2, 0.5),
            'USOIL': (0.5, 1.0),
            'DXY': (0.3, 0.7),
        }
        sl_min, sl_max = SL_RANGE_USD.get(symbol, (1.0 * atr, 2.5 * atr))

        if "BUY" in signal_type:
            fibo_distance = entry - (fibo_info['swing_low'] - atr)   # Distance kỹ thuật
            sl_distance = max(sl_min, min(fibo_distance, sl_max))    # Clamp trong range
            sl = entry - sl_distance
        else:  # SELL
            fibo_distance = (fibo_info['swing_high'] + atr) - entry
            sl_distance = max(sl_min, min(fibo_distance, sl_max))
            sl = entry + sl_distance
    else:
        # ATR-based: SL = entry ± 1×ATR, TP = entry ± 2×ATR
        tp1 = None
        tp3 = None
        if "BUY" in signal_type:
            sl = entry - atr
            tp = entry + (2 * atr)
        else:  # SELL
            sl = entry + atr
            tp = entry - (2 * atr)

    # H1 confirmation string
    if h1_trend:
        if "BUY" in signal_type and h1_trend == "UP":
            confirmation = f"✅ H1 {h1_trend} aligned"
        elif "SELL" in signal_type and h1_trend == "DOWN":
            confirmation = f"✅ H1 {h1_trend} aligned"
        else:
            confirmation = f"⚠️ H1 {h1_trend} (check confluence)"

    # Check volume strength
    vol_info = check_volume_strength(df, lookback=20)

    return {
        'entry': entry,
        'sl': sl,
        'tp': tp,  # Primary TP (TP2 for Fibo, 2×ATR for ATR-based)
        'tp1': tp1,  # TP1: 127.2% extension (Fibo only)
        'tp3': tp3,  # TP3: 200% extension (Fibo only)
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
        'h1_confirmation': confirmation,
        'volume_ratio': vol_info['ratio'],
        'volume_is_strong': vol_info['is_strong'],
        'is_consolidating': cons_info['is_consolidating'],
        'atr': cons_info['atr'],
        'atr_avg': cons_info['atr_avg'],
        'fibo_info': fibo_info  # Fibonacci data if detected
    }


def check_symbol_setup(symbol, timeframe="5m"):
    """Generic scalp setup check for any symbol (BTC, ETH, XAU, XAG, USOIL, DXY).

    Args:
        symbol: 'XAU', 'BTC', 'ETH', 'USOIL', 'XAG', 'DXY'
        timeframe: '5m' or '15m'

    Returns:
        dict with setup details or None
    """
    try:
        df = fetch_symbol(symbol, timeframe, 7)
        df_h1 = fetch_symbol(symbol, "1h", 5)
        setup = find_scalp_entry(df, symbol, df_h1)
        return setup
    except Exception as e:
        logger.error(f"check_symbol_setup {symbol} {timeframe} error: {e}")
        return None


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

                # Phase 2: Volume + Consolidation
                vol_status = "✓ Strong" if setup['volume_is_strong'] else "✗ Weak"
                cons_status = "✓ Yes" if setup['is_consolidating'] else "✗ No"
                lines.append(f"Volume: {vol_status} ({setup['volume_ratio']:.2f}x) | Consolidating: {cons_status}")

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

                # Phase 2: Volume + Consolidation
                vol_status = "✓ Strong" if setup['volume_is_strong'] else "✗ Weak"
                cons_status = "✓ Yes" if setup['is_consolidating'] else "✗ No"
                lines.append(f"Volume: {vol_status} ({setup['volume_ratio']:.2f}x) | Consolidating: {cons_status}")

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
