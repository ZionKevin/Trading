# -*- coding: utf-8 -*-
"""Trading profile learning - track user's trading style."""
import json
import re
from pathlib import Path
from datetime import datetime

PROFILE_FILE = "trading_profile.json"


def parse_teach_text(text):
    """Parse câu dạy bot kiểu gõ tự do — không cần đúng thứ tự, không cần format cứng.

    Chấp nhận đủ kiểu:
        "buy 4150 sl 4140 tp 4170 giá test OB H1 + nến engulfing"
        "4150 4140 4170 test OB"                    (3 số: entry sl tp — kiểu cũ)
        "sell btc 63500 tp 62800 sl 63900 quét liquidity xong CHoCH"
        "mua 4150 dừng 4140 chốt 4170"

    Returns:
        (dict, None) nếu parse được: {entry, sl, tp, direction, symbol, timeframe, reason}
        (None, error_message) nếu thiếu thông tin.
    """
    raw = text.strip()
    low = raw.lower()

    # --- Symbol (default XAU) ---
    symbol = "XAU"
    if re.search(r'\bbtc\b|bitcoin', low):
        symbol = "BTC"

    # --- Timeframe (default M5) — chỉ nhận m5/m15 (h1/h4 thường là ngữ cảnh, giữ trong reason) ---
    timeframe = "M5"
    tf_match = re.search(r'\b(m5|m15)\b', low)
    if tf_match:
        timeframe = tf_match.group(1).upper()

    # --- Direction (optional — sẽ tự suy từ SL nếu không ghi) ---
    direction = None
    if re.search(r'\b(buy|mua|long)\b', low):
        direction = 'BUY'
    elif re.search(r'\b(sell|ban|bán|short)\b', low):
        direction = 'SELL'

    # --- Số có nhãn: sl/stop/dừng, tp/target/chốt, entry/vào/@ ---
    def _labeled(patterns):
        for p in patterns:
            m = re.search(p + r'\s*[:=@]?\s*(\d+(?:[.,]\d+)?)', low)
            if m:
                return float(m.group(1).replace(',', '.')), m.span()
        return None, None

    sl, sl_span = _labeled([r'\bsl\b', r'\bstop\b', r'\bdừng\b', r'\bdung\b'])
    tp, tp_span = _labeled([r'\btp\d?\b', r'\btarget\b', r'\bchốt\b', r'\bchot\b'])
    entry, en_span = _labeled([r'\bentry\b', r'\bvào\b', r'\bvao\b', r'\be\b', r'@'])

    # --- Số trơn (không nhãn) — trừ các số đã match nhãn ---
    used_spans = [s for s in (sl_span, tp_span, en_span) if s]
    bare = []
    for m in re.finditer(r'\d+(?:[.,]\d+)?', low):
        if any(us[0] <= m.start() < us[1] for us in used_spans):
            continue
        val = float(m.group().replace(',', '.'))
        if val >= 10:  # bỏ số nhỏ kiểu "38.2%" hay "m5"... giá XAU/BTC đều >10
            bare.append(val)

    # Điền chỗ trống theo thứ tự: entry → sl → tp
    bare_iter = iter(bare)
    if entry is None:
        entry = next(bare_iter, None)
    if sl is None:
        sl = next(bare_iter, None)
    if tp is None:
        tp = next(bare_iter, None)

    if entry is None or sl is None or tp is None:
        return None, ("Thiếu giá — cần đủ 3 số: entry, SL, TP.\n"
                      "Ví dụ:\n"
                      "  /day buy 4150 sl 4140 tp 4170 test OB H1\n"
                      "  /day 4150 4140 4170 nến engulfing ở FVG\n"
                      "  /day sell btc 63500 sl 63900 tp 62800 CHoCH xong quét liquidity")

    # --- Suy direction từ SL nếu chưa ghi; nếu ghi rồi mà SL/TP ngược → tự đảo giúp ---
    inferred = 'BUY' if sl < entry else 'SELL'
    if direction is None:
        direction = inferred
    elif direction != inferred:
        # User ghi buy nhưng sl > entry → khả năng gõ nhầm chỗ sl/tp → đảo lại
        sl, tp = tp, sl
        if (direction == 'BUY' and sl >= entry) or (direction == 'SELL' and sl <= entry):
            return None, (f"Số không khớp hướng {direction}: entry {entry:g}, SL {sl:g}, TP {tp:g}.\n"
                          f"BUY thì SL < entry < TP, SELL thì ngược lại. Check lại giúp tao.")

    # --- Reason = phần text còn lại sau khi bỏ giá + keyword lệnh ---
    # Chỉ bỏ số >=3 chữ số (giá) — giữ "38.2%", "H1", "TP2"... trong lý do
    reason = raw
    for pat in [r'\b(sl|stop|dừng|dung|tp\d?|target|chốt|chot|entry|vào|vao)\b\s*[:=@]?\s*\d{3,}(?:[.,]\d+)?',
                r'\b\d{3,}(?:[.,]\d+)?\b',
                r'\b(buy|mua|long|sell|ban|bán|short)\b', r'\b(btc|bitcoin)\b',
                r'\b(m5|m15)\b', r'@']:
        reason = re.sub(pat, ' ', reason, flags=re.IGNORECASE)
    reason = re.sub(r'\s+', ' ', reason).strip(' ,.-+|')
    if not reason:
        reason = "(không ghi lý do)"

    return {'entry': entry, 'sl': sl, 'tp': tp, 'direction': direction,
            'symbol': symbol, 'timeframe': timeframe, 'reason': reason}, None


def load_profile():
    """Load trading profile."""
    if Path(PROFILE_FILE).exists():
        with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'trades_taught': [],
        'style_summary': {
            'avg_risk_reward_ratio': 0,
            'preferred_entry_types': [],
            'preferred_confluence': [],
            'avg_entry_price': 0,
            'avg_sl_distance': 0,
            'avg_tp_distance': 0,
            'confidence_level': 0,
            'total_trades': 0
        },
        'last_updated': None
    }


def save_profile(profile):
    """Save trading profile."""
    profile['last_updated'] = datetime.now().isoformat()
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def add_taught_trade(entry, sl, tp, reason, symbol="XAU", timeframe="M5"):
    """Add a trade that user taught to the bot.

    Args:
        entry: Entry price (float)
        sl: Stop loss price (float)
        tp: Take profit price (float)
        reason: User's analysis/reason for entry (string)
        symbol: Trading symbol (default XAU)
        timeframe: Timeframe (default M5)
    """
    profile = load_profile()

    trade = {
        'id': len(profile['trades_taught']) + 1,
        'entry': entry,
        'sl': sl,
        'tp': tp,
        'reason': reason,
        'symbol': symbol,
        'timeframe': timeframe,
        'taught_at': datetime.now().isoformat(),
        'direction': 'BUY' if tp > entry else 'SELL'
    }

    profile['trades_taught'].append(trade)

    # Update style summary
    update_style_summary(profile)

    save_profile(profile)
    return trade


def update_style_summary(profile):
    """Analyze taught trades and update style summary."""
    trades = profile['trades_taught']

    if not trades:
        return

    # Calculate averages
    risk_rewards = []
    for t in trades:
        if t['direction'] == 'BUY':
            risk = abs(t['entry'] - t['sl'])
            reward = abs(t['tp'] - t['entry'])
        else:  # SELL
            risk = abs(t['sl'] - t['entry'])
            reward = abs(t['entry'] - t['tp'])

        if risk > 0:
            rrr = reward / risk
            risk_rewards.append(rrr)

    avg_rrr = sum(risk_rewards) / len(risk_rewards) if risk_rewards else 0

    # Extract entry types from reasons
    entry_types = []
    confluence_keywords = []
    for t in trades:
        reason = t['reason'].lower()

        # Detect entry type (hệ SMC + legacy)
        if 'ob' in reason.split() or 'order block' in reason:
            entry_types.append('Order Block')
        if 'fvg' in reason or 'gap' in reason or 'imbalance' in reason:
            entry_types.append('FVG')
        if 'liquidity' in reason or 'quét' in reason or 'quet' in reason or 'stop hunt' in reason:
            entry_types.append('Liquidity Sweep')
        if 'fibo' in reason:
            entry_types.append('Fibonacci')
        if 'support' in reason or 'hỗ trợ' in reason or 'ho tro' in reason:
            entry_types.append('Support')
        if 'resistance' in reason or 'cản' in reason or 'can' in reason.split():
            entry_types.append('Resistance')
        if 'trendline' in reason:
            entry_types.append('Trendline')

        # Detect confluence keywords
        if 'bos' in reason.split():
            confluence_keywords.append('BOS')
        if 'choch' in reason:
            confluence_keywords.append('CHoCH')
        if any(k in reason for k in ('engulf', 'nhấn chìm', 'pin bar', 'pinbar', 'nến', 'nen ', 'sao mai', 'sao hôm')):
            confluence_keywords.append('Nến xác nhận')
        if 'rejection' in reason or 'wick' in reason:
            confluence_keywords.append('Rejection Candle')
        if 'sóng' in reason or 'song ' in reason or 'elliott' in reason:
            confluence_keywords.append('Elliott Wave')
        if 'discount' in reason or 'premium' in reason:
            confluence_keywords.append('Premium/Discount')
        if 'h1' in reason or 'h4' in reason:
            confluence_keywords.append('HTF Trend')
        if 'trend' in reason or 'nhịp' in reason:
            confluence_keywords.append('Trend Alignment')

    # Count most common
    from collections import Counter
    entry_counter = Counter(entry_types)
    confluence_counter = Counter(confluence_keywords)

    profile['style_summary'] = {
        'avg_risk_reward_ratio': round(avg_rrr, 2),
        'preferred_entry_types': [k for k, v in entry_counter.most_common(3)],
        'preferred_confluence': [k for k, v in confluence_counter.most_common(3)],
        'total_trades': len(trades),
        'avg_entry_per_symbol': round(sum(t['entry'] for t in trades) / len(trades), 2),
        'buy_sell_ratio': f"{sum(1 for t in trades if t['direction']=='BUY')}:{sum(1 for t in trades if t['direction']=='SELL')}",
        'confidence_assessment': get_confidence_assessment(profile)
    }


def get_confidence_assessment(profile):
    """Assess user's trading confidence from taught trades."""
    trades = profile['trades_taught']

    if len(trades) < 3:
        return "Learning phase (need more trades)"

    reasons_detailed = sum(1 for t in trades if len(t['reason']) > 50)
    confluence_count = sum(1 for t in trades if any(x in t['reason'].lower() for x in ['rejection', 'trend', 'h1', 'confluence']))

    if confluence_count >= len(trades) * 0.7:
        return "High - Strong confluence seeker"
    elif reasons_detailed >= len(trades) * 0.6:
        return "Medium-High - Analytical approach"
    else:
        return "Medium - Building methodology"


def format_profile():
    """Format trading profile for display."""
    profile = load_profile()

    if not profile['trades_taught']:
        return "No trades taught yet. Use /teach to start!\nFormat: /teach entry sl tp reason"

    summary = profile['style_summary']

    msg = "📊 YOUR TRADING PROFILE\n"
    msg += f"Total trades taught: {summary['total_trades']}\n"
    msg += f"Risk:Reward ratio: 1:{summary['avg_risk_reward_ratio']}\n"
    msg += f"Buy:Sell: {summary['buy_sell_ratio']}\n\n"

    msg += "🎯 Preferred Entry Types:\n"
    if summary['preferred_entry_types']:
        for entry_type in summary['preferred_entry_types']:
            msg += f"  • {entry_type}\n"
    else:
        msg += "  (Not enough data)\n"

    msg += "\n🔗 Confluence Factors:\n"
    if summary['preferred_confluence']:
        for conf in summary['preferred_confluence']:
            msg += f"  • {conf}\n"
    else:
        msg += "  (Not specified)\n"

    msg += f"\n💪 Confidence: {summary['confidence_assessment']}\n"

    return msg


def list_taught_trades(limit=5):
    """List recently taught trades."""
    profile = load_profile()
    trades = profile['trades_taught'][-limit:]

    if not trades:
        return "No trades taught yet."

    msg = "📈 RECENTLY TAUGHT TRADES\n"
    for t in trades:
        msg += f"\n#{t['id']} {t['direction']} {t['symbol']} ({t['timeframe']})\n"
        msg += f"Entry: {t['entry']:.0f} | SL: {t['sl']:.0f} | TP: {t['tp']:.0f}\n"
        msg += f"Reason: {t['reason'][:60]}...\n" if len(t['reason']) > 60 else f"Reason: {t['reason']}\n"

    return msg


if __name__ == "__main__":
    # Test
    add_taught_trade(4543, 4540, 4570, "Chờ test Fibo 38.2%, rejection wick mạnh, H1 UP", "XAU", "M5")
    add_taught_trade(4550, 4545, 4565, "Support bounce + MA89, trend aligned", "XAU", "M5")
    print(format_profile())
    print("\n" + list_taught_trades())
