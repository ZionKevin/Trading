# -*- coding: utf-8 -*-
"""Trading profile learning - track user's trading style."""
import json
from pathlib import Path
from datetime import datetime

PROFILE_FILE = "trading_profile.json"


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

        # Detect entry type
        if 'fibo' in reason:
            entry_types.append('Fibonacci')
        if 'support' in reason or 'hỗ trợ' in reason:
            entry_types.append('Support')
        if 'resistance' in reason or 'cản' in reason:
            entry_types.append('Resistance')
        if 'ma89' in reason:
            entry_types.append('MA89')
        if 'trendline' in reason:
            entry_types.append('Trendline')

        # Detect confluence keywords
        if 'rejection' in reason or 'wick' in reason:
            confluence_keywords.append('Rejection Candle')
        if 'h1' in reason:
            confluence_keywords.append('H1 Trend')
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
