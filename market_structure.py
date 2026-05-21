# -*- coding: utf-8 -*-
"""Phase 5 Advanced: Market Structure + Rejection Candle Detection."""
import numpy as np
from fetch import fetch_symbol


def detect_rejection_candle(df, index=-1, lookback=5):
    """Detect rejection candles on the last N candles (M15 signal).

    Rejection = high wick + close near open (hammer/inverted hammer pattern)
    Returns: {'is_rejection': bool, 'type': 'BULLISH_REJECTION' or 'BEARISH_REJECTION', 'strength': 0-100}
    """
    if len(df) < 2:
        return {'is_rejection': False, 'type': None, 'strength': 0}

    candle = df.iloc[index]
    open_p = candle['Open']
    close_p = candle['Close']
    high_p = candle['High']
    low_p = candle['Low']

    # Calculate wick sizes
    if close_p > open_p:  # Bullish candle
        upper_wick = high_p - close_p
        lower_wick = open_p - low_p
        body = close_p - open_p
    else:  # Bearish candle
        upper_wick = high_p - open_p
        lower_wick = close_p - low_p
        body = open_p - close_p

    # Rejection if: upper_wick > 1.5x body (strong rejection of move)
    if body > 0:
        wick_ratio = upper_wick / body
    else:
        wick_ratio = 0

    is_rejection = wick_ratio > 1.5  # Strong wick rejection

    # Type: bullish rejection = bearish candle at resistance, bearish rejection = bullish candle at support
    strength = 0
    rejection_type = None

    if is_rejection:
        if close_p < open_p:  # Bearish candle = rejection at resistance (SELL signal)
            rejection_type = "BEARISH_REJECTION"
            strength = min(100, int(wick_ratio * 30))  # Scale to 0-100
        else:  # Bullish candle = rejection at support (BUY signal)
            rejection_type = "BULLISH_REJECTION"
            strength = min(100, int(wick_ratio * 30))

    return {
        'is_rejection': is_rejection,
        'type': rejection_type,
        'strength': strength,
        'wick_ratio': wick_ratio,
        'body_size': body
    }


def detect_support_hold(df, lookback=10):
    """Detect if price is bouncing off support (support hold = bullish).

    Returns: {'is_holding': bool, 'bounces': count, 'confidence': 0-100}
    """
    recent = df.tail(lookback)
    lows = recent['Low'].values
    closes = recent['Close'].values

    # Find support level (lowest low in lookback)
    support = min(lows)
    support_idx = np.argmin(lows)

    # Check if recent candles bounced off support (closed above support)
    bounces = 0
    for i in range(support_idx, len(closes)):
        if closes[i] > support + 1:  # Closed above support (within 1 pip margin)
            bounces += 1

    is_holding = bounces >= 2  # At least 2 closes above support = hold

    # Confidence: how many times did price reject at support?
    confidence = min(100, bounces * 25)

    return {
        'is_holding': is_holding,
        'support_level': support,
        'bounces': bounces,
        'confidence': confidence
    }


def detect_resistance_hold(df, lookback=10):
    """Detect if price is bouncing off resistance (resistance hold = bearish)."""
    recent = df.tail(lookback)
    highs = recent['High'].values
    closes = recent['Close'].values

    resistance = max(highs)
    resistance_idx = np.argmax(highs)

    bounces = 0
    for i in range(resistance_idx, len(closes)):
        if closes[i] < resistance - 1:
            bounces += 1

    is_holding = bounces >= 2

    confidence = min(100, bounces * 25)

    return {
        'is_holding': is_holding,
        'resistance_level': resistance,
        'bounces': bounces,
        'confidence': confidence
    }


def get_last_n_rejections(df, n=3, lookback=20):
    """Get last N rejection candles from the last 'lookback' candles."""
    recent = df.tail(lookback)
    rejections = []

    for i in range(len(recent)):
        rej = detect_rejection_candle(recent, index=i)
        if rej['is_rejection']:
            rejections.append({
                'index': len(df) - lookback + i,
                'time': recent.index[i],
                'type': rej['type'],
                'strength': rej['strength']
            })

    return rejections[-n:] if rejections else []


def should_exit_early(entry_price, current_price, target_tp, rejection_info, is_buy=True):
    """Decide if should exit early due to rejection.

    Args:
        entry_price: entry price
        current_price: current price
        target_tp: target take-profit
        rejection_info: from detect_rejection_candle()
        is_buy: True if BUY trade, False if SELL

    Returns:
        {'should_exit': bool, 'reason': str, 'exit_price': float or None, 'pnl_pct': float}
    """
    pnl = current_price - entry_price if is_buy else entry_price - current_price
    pnl_pct = (pnl / entry_price) * 100 if entry_price != 0 else 0

    # If rejection candle appeared AND price is within 2 pips of TP AND strong rejection
    distance_to_tp = abs(target_tp - current_price)
    within_tp_range = distance_to_tp <= 2  # Within 2 pips of TP

    should_exit = False
    reason = None
    exit_price = None

    if rejection_info['is_rejection'] and within_tp_range and rejection_info['strength'] >= 70:
        # Strong rejection near TP → exit now, take 80-90% profit
        exit_price = current_price
        should_exit = True
        reason = f"Strong rejection ({rejection_info['strength']}/100) near TP, exit {pnl_pct:.2f}% profit"

    elif rejection_info['is_rejection'] and pnl > 0 and rejection_info['strength'] >= 80:
        # Extremely strong rejection + already in profit → exit immediately
        exit_price = current_price
        should_exit = True
        reason = f"Extreme rejection ({rejection_info['strength']}/100), secure {pnl_pct:.2f}% profit"

    return {
        'should_exit': should_exit,
        'reason': reason,
        'exit_price': exit_price,
        'pnl_pct': pnl_pct,
        'current_pnl': pnl
    }


def calculate_optimal_sl_tp(entry_price, direction, symbol, target_risk_dollars=200):
    """Calculate SL/TP to hit exact risk target ($200-250).

    Args:
        entry_price: entry price
        direction: 'BUY' or 'SELL'
        symbol: 'XAU', 'BTC', etc. (to get ATR)
        target_risk_dollars: target risk in dollars ($200-250)

    Returns:
        {'sl': float, 'tp': float, 'risk_dollars': float, 'reward_dollars': float, 'rrr': float}
    """
    try:
        df = fetch_symbol(symbol, "5m", 5)
        current_atr = df['High'].iloc[-1] - df['Low'].iloc[-1]
        atr_avg = (df['High'] - df['Low']).tail(20).mean()

        # Use ATR but adjust for target risk
        # Risk per pip for XAU = $10, others need conversion
        risk_per_pip = 10 if symbol == "XAU" else 1  # Simplified

        # Calculate SL distance needed to hit target risk
        sl_distance = target_risk_dollars / (risk_per_pip * 0.2)  # 0.2 lot size

        # TP distance = 2x SL (1:2 ratio)
        tp_distance = sl_distance * 2

        if direction == "BUY":
            sl = entry_price - sl_distance
            tp = entry_price + tp_distance
        else:  # SELL
            sl = entry_price + sl_distance
            tp = entry_price - tp_distance

        risk_dollars = sl_distance * risk_per_pip * 0.2
        reward_dollars = tp_distance * risk_per_pip * 0.2
        rrr = reward_dollars / risk_dollars if risk_dollars > 0 else 0

        return {
            'sl': sl,
            'tp': tp,
            'risk_dollars': risk_dollars,
            'reward_dollars': reward_dollars,
            'rrr': rrr,
            'sl_distance': sl_distance,
            'tp_distance': tp_distance
        }

    except Exception as e:
        print(f"Error calculating optimal SL/TP: {e}")
        return None


def detect_fibonacci_bounce(df, lookback=30):
    """Detect Fibonacci retracement bounce (38.2% + 61.8%).

    Finds swing high/low, calculates Fibo levels, checks if price bounced off them.

    Returns:
        dict: {
            'fibo_level': float (38.2 or 61.8),
            'fibo_price': float (exact Fibo level price),
            'swing_high': float,
            'swing_low': float,
            'direction': 'UP' (bounce from support) or 'DOWN' (bounce from resistance),
            'entry': float (current price),
            'tp_extension': float (127.2% Fibo extension)
        }
        or None if no valid bounce detected
    """
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent['High'].values
    lows = recent['Low'].values

    # Find swing high/low
    swing_high = max(highs)
    swing_low = min(lows)

    if swing_high == swing_low:
        return None

    current_price = df['Close'].iloc[-1]

    # Calculate Fibo retracement levels (100% = swing range)
    fibo_range = swing_high - swing_low
    fibo_38_price = swing_high - (fibo_range * 0.382)  # 38.2%
    fibo_61_price = swing_high - (fibo_range * 0.618)  # 61.8%

    # Detect bounce: price near Fibo level (±2 pips tolerance)
    tolerance = 2
    touch_38 = abs(current_price - fibo_38_price) <= tolerance
    touch_61 = abs(current_price - fibo_61_price) <= tolerance

    if not (touch_38 or touch_61):
        return None

    # Determine direction (BUY = bounce from low, SELL = bounce from high)
    # If current price > middle of range → bouncing from support (BUY)
    # If current price < middle of range → bouncing from resistance (SELL)
    middle = (swing_high + swing_low) / 2

    if current_price > middle:
        # BUY bounce from support (lower Fibo level)
        fibo_level = 61.8 if touch_61 else 38.2
        fibo_price = fibo_61_price if touch_61 else fibo_38_price

        # TP at 127.2% extension (above swing high)
        extension_range = fibo_range * 1.272
        tp_extension = swing_high + (extension_range - fibo_range)

        direction = 'UP'
    else:
        # SELL bounce from resistance (higher Fibo level)
        fibo_level = 61.8 if touch_61 else 38.2
        fibo_price = fibo_61_price if touch_61 else fibo_38_price

        # TP at 127.2% extension (below swing low)
        extension_range = fibo_range * 1.272
        tp_extension = swing_low - (extension_range - fibo_range)

        direction = 'DOWN'

    return {
        'fibo_level': fibo_level,
        'fibo_price': fibo_price,
        'swing_high': swing_high,
        'swing_low': swing_low,
        'direction': direction,
        'entry': current_price,
        'tp_extension': tp_extension
    }


def detect_fibo_rejection_confluence(df, fibo_info, lookback_rejection=3):
    """Detect confluence: Fibo bounce + rejection candle (high wick bounce).

    Checks if recent candles show rejection pattern at Fibo level.
    High wick ratio = strong rejection from level = high quality setup.

    Args:
        df: DataFrame with OHLCV
        fibo_info: From detect_fibonacci_bounce()
        lookback_rejection: Check last N candles for rejection (default 3)

    Returns:
        dict: {
            'has_confluence': bool,
            'rejection_strength': 0-100,
            'rejection_type': 'BULLISH_REJECTION' or 'BEARISH_REJECTION' or None,
            'wick_ratio': float
        }
    """
    if not fibo_info or len(df) < lookback_rejection + 1:
        return {'has_confluence': False, 'rejection_strength': 0, 'rejection_type': None, 'wick_ratio': 0}

    recent = df.tail(lookback_rejection)
    has_rejection = False
    max_wick_ratio = 0
    rejection_type = None

    for i in range(len(recent)):
        candle = recent.iloc[i]
        open_p = candle['Open']
        close_p = candle['Close']
        high_p = candle['High']
        low_p = candle['Low']

        # Calculate wick size
        if close_p > open_p:  # Bullish candle
            upper_wick = high_p - close_p
            lower_wick = open_p - low_p
            body = close_p - open_p
        else:  # Bearish candle
            upper_wick = high_p - open_p
            lower_wick = close_p - low_p
            body = open_p - close_p

        if body > 0:
            wick_ratio = max(upper_wick, lower_wick) / body
        else:
            wick_ratio = 0

        # Check for strong wick rejection (ratio > 1.5)
        if wick_ratio > 1.5:
            max_wick_ratio = max(max_wick_ratio, wick_ratio)
            has_rejection = True

            # Determine rejection type
            if fibo_info['direction'] == 'UP':  # BUY setup
                # Bullish rejection = close_p > open_p with lower wick at support
                if close_p > open_p and lower_wick > upper_wick:
                    rejection_type = 'BULLISH_REJECTION'
            else:  # SELL setup
                # Bearish rejection = close_p < open_p with upper wick at resistance
                if close_p < open_p and upper_wick > lower_wick:
                    rejection_type = 'BEARISH_REJECTION'

    rejection_strength = min(100, int(max_wick_ratio * 25)) if has_rejection else 0

    return {
        'has_confluence': has_rejection,
        'rejection_strength': rejection_strength,
        'rejection_type': rejection_type,
        'wick_ratio': max_wick_ratio
    }


def format_market_structure_alert(symbol, setup, rejection_info, support_info, m15_df):
    """Format alert with market structure context."""
    msg = f"\n[MARKET STRUCTURE ANALYSIS]\n"

    # Rejection candle status
    if rejection_info['is_rejection']:
        msg += f"Rejection: {rejection_info['type']} (strength {rejection_info['strength']}/100)\n"
    else:
        msg += f"No rejection yet\n"

    # Support/resistance hold
    if support_info['is_holding']:
        msg += f"Support holding: {support_info['bounces']} bounces\n"

    # Recent rejections
    rejections = get_last_n_rejections(m15_df, n=2)
    if rejections:
        msg += f"Recent rejections: {len(rejections)} on M15\n"

    return msg


if __name__ == "__main__":
    # Test
    df = fetch_symbol("XAU", "15m", 5)
    rej = detect_rejection_candle(df)
    print(f"Last candle rejection: {rej}")

    sup = detect_support_hold(df)
    print(f"Support hold: {sup}")

    opt_sl_tp = calculate_optimal_sl_tp(4550, "BUY", "XAU", 200)
    print(f"Optimal SL/TP for $200 risk: {opt_sl_tp}")
