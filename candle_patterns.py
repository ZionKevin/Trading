# -*- coding: utf-8 -*-
"""Nến Nhật (candlestick patterns) — xác nhận entry cho hệ SMC.

Ngưỡng theo ATR/range của chính nến, không dùng số $ cứng → dùng chung XAU và BTC.
Strength: 3 = mạnh nhất (engulfing, sao mai/hôm), 2 = pin bar, 1 = inside bar/doji.
"""
from smc_structure import calc_atr


def _candle(df, i):
    """Trích 1 nến thành dict tiện tính toán."""
    o = float(df['Open'].iloc[i])
    h = float(df['High'].iloc[i])
    l = float(df['Low'].iloc[i])
    c = float(df['Close'].iloc[i])
    body = abs(c - o)
    rng = max(h - l, 1e-9)
    return {
        'open': o, 'high': h, 'low': l, 'close': c,
        'body': body, 'range': rng,
        'upper_wick': h - max(o, c),
        'lower_wick': min(o, c) - l,
        'bull': c > o, 'bear': c < o,
    }


def is_bullish_engulfing(prev, cur, atr):
    """Nến tăng nhấn chìm toàn bộ thân nến giảm trước — đảo chiều tăng mạnh."""
    return (prev['bear'] and cur['bull']
            and cur['close'] >= prev['open'] and cur['open'] <= prev['close']
            and cur['body'] >= 0.8 * prev['body']
            and cur['body'] >= 0.3 * atr)


def is_bearish_engulfing(prev, cur, atr):
    return (prev['bull'] and cur['bear']
            and cur['close'] <= prev['open'] and cur['open'] >= prev['close']
            and cur['body'] >= 0.8 * prev['body']
            and cur['body'] >= 0.3 * atr)


def is_bullish_pinbar(cur, atr):
    """Hammer: râu dưới dài >= 2× thân, close nằm ở 1/3 trên của nến — từ chối giá xuống."""
    return (cur['lower_wick'] >= 2 * cur['body']
            and cur['lower_wick'] >= 0.4 * atr
            and (cur['close'] - cur['low']) / cur['range'] >= 0.6)


def is_bearish_pinbar(cur, atr):
    """Shooting star: râu trên dài, close ở 1/3 dưới — từ chối giá lên."""
    return (cur['upper_wick'] >= 2 * cur['body']
            and cur['upper_wick'] >= 0.4 * atr
            and (cur['high'] - cur['close']) / cur['range'] >= 0.6)


def is_morning_star(c1, c2, c3, atr):
    """Sao mai (3 nến): giảm mạnh → nến nhỏ lưỡng lự → tăng mạnh close quá nửa nến 1."""
    return (c1['bear'] and c1['body'] >= 0.4 * atr
            and c2['body'] <= 0.5 * c1['body']
            and c3['bull'] and c3['close'] > (c1['open'] + c1['close']) / 2)


def is_evening_star(c1, c2, c3, atr):
    """Sao hôm: tăng mạnh → nến nhỏ → giảm mạnh close quá nửa nến 1."""
    return (c1['bull'] and c1['body'] >= 0.4 * atr
            and c2['body'] <= 0.5 * c1['body']
            and c3['bear'] and c3['close'] < (c1['open'] + c1['close']) / 2)


def is_inside_bar(prev, cur):
    """Inside bar: nến nằm gọn trong range nến trước — nén lực chờ break."""
    return cur['high'] <= prev['high'] and cur['low'] >= prev['low']


def is_doji(cur):
    return cur['body'] <= 0.12 * cur['range']


# Tên tiếng Việt để hiển thị trong alert
PATTERN_NAMES_VI = {
    'BULL_ENGULF': 'Nến nhấn chìm tăng (Bullish Engulfing)',
    'BEAR_ENGULF': 'Nến nhấn chìm giảm (Bearish Engulfing)',
    'BULL_PINBAR': 'Pin bar tăng (Hammer — từ chối giá xuống)',
    'BEAR_PINBAR': 'Pin bar giảm (Shooting Star — từ chối giá lên)',
    'MORNING_STAR': 'Sao mai (Morning Star)',
    'EVENING_STAR': 'Sao hôm (Evening Star)',
    'INSIDE_BAR': 'Inside bar (nén lực)',
    'DOJI': 'Doji (lưỡng lự)',
}


def detect_confirmation(df, direction='UP'):
    """Tìm nến xác nhận theo hướng trên 2 nến gần nhất.

    Args:
        df: OHLCV dataframe (nến cuối = nến hiện tại)
        direction: 'UP' cần xác nhận tăng, 'DOWN' cần xác nhận giảm

    Returns:
        {'pattern': str, 'name_vi': str, 'strength': 1-3} hoặc None
    """
    if len(df) < 4:
        return None

    atr = calc_atr(df)
    c_now = _candle(df, -1)
    c_prev = _candle(df, -2)
    c_prev2 = _candle(df, -3)

    found = []
    if direction == 'UP':
        if is_morning_star(c_prev2, c_prev, c_now, atr):
            found.append(('MORNING_STAR', 3))
        if is_bullish_engulfing(c_prev, c_now, atr):
            found.append(('BULL_ENGULF', 3))
        if is_bullish_pinbar(c_now, atr):
            found.append(('BULL_PINBAR', 2))
        elif is_bullish_pinbar(c_prev, atr) and c_now['bull']:
            found.append(('BULL_PINBAR', 2))
        if is_inside_bar(c_prev, c_now) and c_now['bull']:
            found.append(('INSIDE_BAR', 1))
    else:
        if is_evening_star(c_prev2, c_prev, c_now, atr):
            found.append(('EVENING_STAR', 3))
        if is_bearish_engulfing(c_prev, c_now, atr):
            found.append(('BEAR_ENGULF', 3))
        if is_bearish_pinbar(c_now, atr):
            found.append(('BEAR_PINBAR', 2))
        elif is_bearish_pinbar(c_prev, atr) and c_now['bear']:
            found.append(('BEAR_PINBAR', 2))
        if is_inside_bar(c_prev, c_now) and c_now['bear']:
            found.append(('INSIDE_BAR', 1))

    if not found:
        return None
    pattern, strength = max(found, key=lambda x: x[1])
    return {'pattern': pattern, 'name_vi': PATTERN_NAMES_VI[pattern], 'strength': strength}
