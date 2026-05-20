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
