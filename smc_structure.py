# -*- coding: utf-8 -*-
"""SMC (Smart Money Concepts) core: swing structure, BOS/CHoCH, Order Block, FVG, liquidity.

Tất cả ngưỡng đều tính theo ATR (không dùng số $ cứng) → dùng chung được cho XAU và BTC.
"""
import numpy as np


def calc_atr(df, period=14):
    """True-range ATR (chuẩn hơn High-Low đơn thuần)."""
    high, low, close = df['High'], df['Low'], df['Close']
    prev_close = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
    atr = float(tr.tail(period).mean())
    return atr if atr > 0 else float((high - low).tail(period).mean())


def find_swings(df, left=3, right=3):
    """Fractal swing high/low: đỉnh/đáy cao/thấp nhất trong cửa sổ left+right nến.

    Returns:
        list (theo thứ tự thời gian, đảm bảo HIGH/LOW xen kẽ):
        {'type': 'HIGH'|'LOW', 'price': float, 'i': int, 'time': timestamp}
    """
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    swings = []

    for i in range(left, n - right):
        win_h = highs[i - left:i + right + 1]
        win_l = lows[i - left:i + right + 1]
        if highs[i] >= win_h.max() and (win_h >= highs[i]).sum() == 1:
            swings.append({'type': 'HIGH', 'price': float(highs[i]), 'i': i, 'time': df.index[i]})
        elif lows[i] <= win_l.min() and (win_l <= lows[i]).sum() == 1:
            swings.append({'type': 'LOW', 'price': float(lows[i]), 'i': i, 'time': df.index[i]})

    # Ép xen kẽ HIGH/LOW: 2 swing cùng loại liên tiếp → giữ cái cực trị hơn
    cleaned = []
    for s in swings:
        if cleaned and cleaned[-1]['type'] == s['type']:
            if (s['type'] == 'HIGH' and s['price'] >= cleaned[-1]['price']) or \
               (s['type'] == 'LOW' and s['price'] <= cleaned[-1]['price']):
                cleaned[-1] = s
        else:
            cleaned.append(s)
    return cleaned


def analyze_structure(df, left=3, right=3):
    """Phân tích cấu trúc: label HH/HL/LH/LL + phát hiện BOS/CHoCH theo close.

    BOS  (Break of Structure): close phá swing THUẬN hướng trend hiện tại → tiếp diễn.
    CHoCH (Change of Character): close phá swing NGƯỢC hướng trend → tín hiệu đảo chiều sớm.

    Returns dict:
        trend: 'UP'|'DOWN'|'RANGE' (theo event cuối)
        last_event: {'event': 'BOS_UP'|'CHOCH_UP'|'BOS_DOWN'|'CHOCH_DOWN', 'price', 'i', 'time'} | None
        events: list toàn bộ events
        swings: swings đã label ('HH'/'HL'/'LH'/'LL')
        last_swing_high / last_swing_low: swing gần nhất CHƯA bị phá (None nếu đã phá)
        range_high / range_low: dealing range hiện tại (swing high/low gần nhất)
        atr: ATR(14)
    """
    swings = find_swings(df, left, right)
    atr = calc_atr(df)

    result = {
        'trend': 'RANGE', 'last_event': None, 'events': [],
        'swings': [], 'last_swing_high': None, 'last_swing_low': None,
        'range_high': None, 'range_low': None, 'atr': atr,
    }
    if len(swings) < 3:
        return result

    # Label HH/HL/LH/LL
    labeled = []
    prev_high = None
    prev_low = None
    for s in swings:
        s = dict(s)
        if s['type'] == 'HIGH':
            s['label'] = 'HH' if (prev_high is not None and s['price'] > prev_high) else 'LH'
            prev_high = s['price']
        else:
            s['label'] = 'LL' if (prev_low is not None and s['price'] < prev_low) else 'HL'
            prev_low = s['price']
        labeled.append(s)
    result['swings'] = labeled

    # State machine: quét từng nến, so close với swing gần nhất đã CONFIRM
    # (swing tại i chỉ confirm sau i+right nến — tránh nhìn trước tương lai)
    closes = df['Close'].values
    events = []
    direction = None       # trend hiện tại theo event
    pending = list(labeled)
    last_sh = None         # swing high chưa bị phá
    last_sl = None         # swing low chưa bị phá
    p_idx = 0

    for i in range(len(df)):
        while p_idx < len(pending) and pending[p_idx]['i'] + right <= i:
            s = pending[p_idx]
            if s['type'] == 'HIGH':
                last_sh = s
            else:
                last_sl = s
            p_idx += 1

        c = closes[i]
        if last_sh is not None and c > last_sh['price']:
            ev_name = 'CHOCH_UP' if direction == 'DOWN' else 'BOS_UP'
            events.append({'event': ev_name, 'price': last_sh['price'], 'i': i, 'time': df.index[i]})
            direction = 'UP'
            last_sh = None
        elif last_sl is not None and c < last_sl['price']:
            ev_name = 'CHOCH_DOWN' if direction == 'UP' else 'BOS_DOWN'
            events.append({'event': ev_name, 'price': last_sl['price'], 'i': i, 'time': df.index[i]})
            direction = 'DOWN'
            last_sl = None

    result['events'] = events
    result['last_event'] = events[-1] if events else None
    result['trend'] = direction if direction else 'RANGE'
    result['last_swing_high'] = last_sh
    result['last_swing_low'] = last_sl

    # Dealing range = swing high + swing low gần nhất (để tính premium/discount)
    recent_highs = [s for s in labeled if s['type'] == 'HIGH']
    recent_lows = [s for s in labeled if s['type'] == 'LOW']
    if recent_highs:
        result['range_high'] = recent_highs[-1]['price']
    if recent_lows:
        result['range_low'] = recent_lows[-1]['price']

    return result


def premium_discount(price, range_high, range_low):
    """Vị trí giá trong dealing range: DISCOUNT (mua rẻ) / PREMIUM (bán đắt) / EQUILIBRIUM."""
    if range_high is None or range_low is None or range_high <= range_low:
        return 'UNKNOWN'
    mid = (range_high + range_low) / 2
    band = (range_high - range_low) * 0.05  # ±5% quanh mid = equilibrium
    if price < mid - band:
        return 'DISCOUNT'
    elif price > mid + band:
        return 'PREMIUM'
    return 'EQUILIBRIUM'


def find_order_blocks(df, events, direction='UP', max_lookback_bars=150, max_blocks=3):
    """Order Block: nến NGƯỢC màu cuối cùng ngay trước cú đẩy tạo BOS/CHoCH.

    Bullish OB (direction=UP): nến giảm cuối trước impulse phá đỉnh — smart money gom hàng.
    OB chỉ valid khi CHƯA mitigated (giá chưa close xuyên hẳn qua zone).

    Returns: list zones mới nhất trước, mỗi zone:
        {'top', 'bottom', 'i', 'time', 'event', 'tapped': bool}
    """
    opens = df['Open'].values
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)

    suffix = '_UP' if direction == 'UP' else '_DOWN'
    target_events = [e for e in events if e['event'].endswith(suffix) and e['i'] >= n - max_lookback_bars]

    blocks = []
    used_idx = set()
    for ev in reversed(target_events):
        j = ev['i']
        # Lùi từ nến break tìm nến ngược màu gần nhất (tối đa 15 nến)
        k = None
        for m in range(j, max(-1, j - 15), -1):
            if direction == 'UP' and closes[m] < opens[m]:
                k = m
                break
            if direction == 'DOWN' and closes[m] > opens[m]:
                k = m
                break
        if k is None or k in used_idx:
            continue
        used_idx.add(k)

        top, bottom = float(highs[k]), float(lows[k])

        # Mitigated: sau khi hình thành, giá đã CLOSE xuyên hẳn qua phía kia của zone
        if direction == 'UP':
            mitigated = any(closes[m] < bottom for m in range(j + 1, n))
        else:
            mitigated = any(closes[m] > top for m in range(j + 1, n))
        if mitigated:
            continue

        # Tapped: giá đã quay lại chạm zone sau khi break chưa
        if direction == 'UP':
            tapped = any(lows[m] <= top for m in range(j + 1, n))
        else:
            tapped = any(highs[m] >= bottom for m in range(j + 1, n))

        blocks.append({'top': top, 'bottom': bottom, 'i': k, 'time': df.index[k],
                       'event': ev['event'], 'tapped': tapped})
        if len(blocks) >= max_blocks:
            break

    return blocks


def find_fvg(df, direction='UP', lookback=80, min_size_atr=0.3):
    """Fair Value Gap (imbalance 3 nến): gap giữa high nến 1 và low nến 3 (bull).

    Chỉ trả gap CHƯA bị fill hoàn toàn, size >= min_size_atr × ATR (bỏ gap li ti).
    Returns: list mới nhất trước: {'top', 'bottom', 'i', 'time'}
    """
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    atr = calc_atr(df)
    min_size = min_size_atr * atr

    gaps = []
    start = max(1, n - lookback)
    for i in range(start, n - 1):
        if direction == 'UP':
            bottom, top = float(highs[i - 1]), float(lows[i + 1])
            if top - bottom < min_size:
                continue
            # Filled: giá sau đó đã quét xuống hết đáy gap
            filled = any(lows[m] <= bottom for m in range(i + 2, n))
        else:
            bottom, top = float(highs[i + 1]), float(lows[i - 1])
            if top - bottom < min_size:
                continue
            filled = any(highs[m] >= top for m in range(i + 2, n))
        if not filled:
            gaps.append({'top': top, 'bottom': bottom, 'i': i, 'time': df.index[i]})

    gaps.reverse()
    return gaps


def find_liquidity_pools(structure, price, atr, side='ABOVE', eq_tol_atr=0.25):
    """Liquidity pools = cụm equal highs/lows + swing extremes — nơi gom stoploss.

    side='ABOVE': pools phía trên giá (target cho lệnh BUY / stop hunt của SELL).
    Returns: list giá tăng dần (ABOVE) / giảm dần (BELOW), gần giá nhất trước.
    """
    swings = structure.get('swings', [])
    tol = eq_tol_atr * atr

    if side == 'ABOVE':
        levels = sorted(set(s['price'] for s in swings if s['type'] == 'HIGH' and s['price'] > price))
    else:
        levels = sorted(set(s['price'] for s in swings if s['type'] == 'LOW' and s['price'] < price), reverse=True)

    # Gộp các level sát nhau (equal highs/lows) thành 1 pool
    pools = []
    for lv in levels:
        if pools and abs(lv - pools[-1]) <= tol:
            pools[-1] = (pools[-1] + lv) / 2  # gộp trung bình
        else:
            pools.append(lv)
    return pools


# ============================================================
# Phase 10.3 — Session liquidity (Asian range sweep) + Killzone + Fibo OTE
# ============================================================

# Giờ UTC. Phiên Á 0-7 UTC (7h-14h VN). London Killzone 7-10 UTC (14h-17h VN),
# NY Killzone 12-15 UTC (19h-22h VN) — theo khung ICT kinh điển.
ASIAN_START, ASIAN_END = 0, 7
LONDON_KZ = (7, 10)
NY_KZ = (12, 15)


def asian_range(df, ref_ts):
    """High/Low phiên Á (0-7h UTC) của NGÀY ref_ts. Index df phải là UTC naive.

    Returns {'high', 'low', 'bars'} hoặc None nếu chưa đủ nến (chưa qua phiên Á).
    """
    try:
        date = ref_ts.date()
    except AttributeError:
        return None
    mask = (df.index.date == date) & (df.index.hour >= ASIAN_START) & (df.index.hour < ASIAN_END)
    bars = df[mask]
    if len(bars) < 6:  # dưới 6 nến (30' M5) = range chưa có nghĩa
        return None
    return {'high': float(bars['High'].max()), 'low': float(bars['Low'].min()),
            'bars': len(bars)}


def detect_asian_sweep(df, ar, direction, ref_ts):
    """Judas swing: sau phiên Á, giá QUÉT đáy (BUY) / đỉnh (SELL) Asian range
    rồi thu hồi lại chưa? — liquidity grab kinh điển lúc London/NY mở cửa.

    BUY:  có nến sau 7h UTC low < asian_low, và close hiện tại đã đòi lại trên asian_low.
    SELL: có nến sau 7h UTC high > asian_high, và close hiện tại đã tụt lại dưới asian_high.
    """
    if ar is None or ref_ts.hour < ASIAN_END:
        return False  # còn trong phiên Á — chưa có chuyện quét
    date = ref_ts.date()
    post = df[(df.index.date == date) & (df.index.hour >= ASIAN_END)]
    if post.empty:
        return False
    close = float(df['Close'].iloc[-1])
    if direction == 'UP':
        return float(post['Low'].min()) < ar['low'] and close > ar['low']
    else:
        return float(post['High'].max()) > ar['high'] and close < ar['high']


def in_killzone(ref_ts):
    """Đang trong killzone không? Returns 'LONDON' | 'NY' | None."""
    try:
        h = ref_ts.hour
    except AttributeError:
        return None
    if LONDON_KZ[0] <= h < LONDON_KZ[1]:
        return 'LONDON'
    if NY_KZ[0] <= h < NY_KZ[1]:
        return 'NY'
    return None


def fibo_ote(price_level, range_high, range_low, direction):
    """OTE (Optimal Trade Entry) — vùng hồi Fibo 61.8%-79% của dealing range.

    BUY: sau leg tăng low→high, pullback về 61.8-79% (tính từ high xuống)
         = dải [low + 21% range, low + 38.2% range].
    Đây là Fibo theo kiểu ICT/SMC — dùng làm confluence, KHÔNG phải hệ signal riêng.
    """
    if range_high is None or range_low is None:
        return False
    rng = range_high - range_low
    if rng <= 0:
        return False
    if direction == 'UP':
        lo, hi = range_low + 0.21 * rng, range_low + 0.382 * rng
    else:
        lo, hi = range_high - 0.382 * rng, range_high - 0.21 * rng
    return lo <= price_level <= hi
