# -*- coding: utf-8 -*-
"""Phase 5: Self-learning framework - track signals, auto-optimize."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from trade_log import load_trades

LEARNING_FILE = "learning.json"
MIN_TRADES_PER_SIGNAL = 5  # Need at least 5 trades to evaluate signal


def load_learning():
    """Load learning data."""
    if Path(LEARNING_FILE).exists():
        with open(LEARNING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'signals': {},
        'symbols': {},
        'hours': {},
        'last_update': None,
        'disabled_signals': []
    }


def save_learning(data):
    """Save learning data."""
    with open(LEARNING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def learn_from_trades():
    """Analyze all trades, extract patterns, update learning database."""
    trades = load_trades()
    learning = load_learning()

    if not trades:
        return learning

    closed_trades = [t for t in trades if t['status'] == 'CLOSED']
    if not closed_trades:
        return learning

    # Reset signals data (recalculate from trades)
    learning['signals'] = {}

    # Analyze per-signal
    for trade in closed_trades:
        sig = trade.get('signal', 'UNKNOWN')
        is_win = trade['pnl'] > 0

        if sig not in learning['signals']:
            learning['signals'][sig] = {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'rrr': 0,
                'enabled': True,
                'confidence': 0,  # 0-100: higher = more confident
                'last_trade': None
            }

        sig_data = learning['signals'][sig]
        sig_data['total'] += 1
        sig_data['total_pnl'] += trade['pnl']
        sig_data['last_trade'] = trade['entry_time']

        if is_win:
            sig_data['wins'] += 1
        else:
            sig_data['losses'] += 1

    # Calculate stats per signal
    for sig, data in learning['signals'].items():
        if data['total'] > 0:
            data['win_rate'] = (data['wins'] / data['total']) * 100

        # Only evaluate if enough trades
        if data['total'] >= MIN_TRADES_PER_SIGNAL:
            wins = [t for t in closed_trades if t.get('signal') == sig and t['pnl'] > 0]
            losses = [t for t in closed_trades if t.get('signal') == sig and t['pnl'] < 0]

            if wins:
                data['avg_win'] = sum(t['pnl'] for t in wins) / len(wins)
            if losses:
                data['avg_loss'] = abs(sum(t['pnl'] for t in losses) / len(losses))
            if data['avg_loss'] > 0:
                data['rrr'] = data['avg_win'] / data['avg_loss']

            # Calculate confidence (0-100)
            # Based on: win_rate (0-50 pts), volume of trades (0-30 pts), consistency (0-20 pts)
            confidence = 0
            if data['win_rate'] >= 60:
                confidence += 50
            elif data['win_rate'] >= 50:
                confidence += 35
            elif data['win_rate'] >= 40:
                confidence += 20
            else:
                confidence += 5

            if data['total'] >= 20:
                confidence += 30
            elif data['total'] >= 10:
                confidence += 20
            elif data['total'] >= 5:
                confidence += 10

            # Consistency: check recent trades
            recent = [t for t in closed_trades if t.get('signal') == sig][-5:]
            if recent:
                recent_wr = sum(1 for t in recent if t['pnl'] > 0) / len(recent) * 100
                if recent_wr >= 60:
                    confidence += 20
                elif recent_wr >= 40:
                    confidence += 10
                else:
                    confidence += 0

            data['confidence'] = min(100, confidence)

            # Auto-disable low confidence signals
            if data['win_rate'] < 35 and data['total'] >= MIN_TRADES_PER_SIGNAL:
                data['enabled'] = False

    # Analyze per-symbol
    learning['symbols'] = {}
    for trade in closed_trades:
        sym = trade.get('symbol', 'UNKNOWN') if 'symbol' in trade else 'XAU'
        is_win = trade['pnl'] > 0

        if sym not in learning['symbols']:
            learning['symbols'][sym] = {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0}

        sym_data = learning['symbols'][sym]
        sym_data['total'] += 1
        sym_data['total_pnl'] += trade['pnl']
        if is_win:
            sym_data['wins'] += 1
        else:
            sym_data['losses'] += 1

    for sym, data in learning['symbols'].items():
        if data['total'] > 0:
            data['win_rate'] = (data['wins'] / data['total']) * 100

    # Update timestamp
    learning['last_update'] = datetime.now().isoformat()

    save_learning(learning)
    return learning


def analyze_context_patterns():
    """Analyze what contexts lead to wins (H1 trend, volume, time of day)."""
    trades = load_trades()
    learning = load_learning()

    if not trades:
        return {}

    closed_trades = [t for t in trades if t['status'] == 'CLOSED']
    if not closed_trades:
        return {}

    patterns = {
        'h1_trends': {},  # H1=UP/DOWN/NEUTRAL: win rate
        'volume_levels': {},  # volume_ratio: win rate
        'hours': {},  # hour of day: win rate
        'symbols': {},  # per symbol: top signals
        'recommendations': []
    }

    # H1 Trend analysis (simplified - check entry_time hour as proxy)
    for signal in learning['signals'].keys():
        sig_trades = [t for t in closed_trades if t.get('signal') == signal]
        if len(sig_trades) >= 5:
            wr = sum(1 for t in sig_trades if t['pnl'] > 0) / len(sig_trades) * 100

            # Recommendation logic
            if wr >= 65:
                patterns['recommendations'].append(f"KEEP {signal}: {wr:.0f}% WR (high confidence)")
            elif wr <= 35:
                patterns['recommendations'].append(f"DISABLE {signal}: {wr:.0f}% WR (too risky)")
            elif wr >= 50:
                patterns['recommendations'].append(f"WATCH {signal}: {wr:.0f}% WR (neutral, test more)")

    # Symbol ranking
    for sym in learning['symbols'].keys():
        sym_data = learning['symbols'][sym]
        if sym_data['total'] >= 5:
            patterns['symbols'][sym] = {
                'win_rate': sym_data['win_rate'],
                'total': sym_data['total'],
                'rank': 'STRONG' if sym_data['win_rate'] >= 60 else 'MEDIUM' if sym_data['win_rate'] >= 50 else 'WEAK'
            }

    # Time of day analysis
    for trade in closed_trades:
        try:
            entry_hour = int(trade['entry_time'].split('T')[1].split(':')[0])
            is_win = trade['pnl'] > 0

            if entry_hour not in patterns['hours']:
                patterns['hours'][entry_hour] = {'wins': 0, 'total': 0}

            patterns['hours'][entry_hour]['total'] += 1
            if is_win:
                patterns['hours'][entry_hour]['wins'] += 1
        except (ValueError, IndexError):
            # Skip if entry_time format is invalid
            pass

    # Calculate hour win rates
    for hour, data in patterns['hours'].items():
        if data['total'] > 0:
            data['win_rate'] = (data['wins'] / data['total']) * 100

    return patterns


def generate_recommendations():
    """Generate auto-learning recommendations based on patterns."""
    patterns = analyze_context_patterns()

    if not patterns.get('recommendations'):
        return None

    msg = "AUTO-LEARNING RECOMMENDATIONS:\n"
    msg += "=" * 40 + "\n"

    # Signal recommendations
    if patterns['recommendations']:
        for rec in patterns['recommendations'][:5]:  # Top 5
            msg += f"  {rec}\n"

    # Symbol recommendations
    strong_syms = [s for s, d in patterns['symbols'].items() if d['rank'] == 'STRONG']
    if strong_syms:
        msg += f"\nTop Symbols: {', '.join(strong_syms)}\n"

    # Best trading hours
    if patterns['hours']:
        best_hours = sorted(patterns['hours'].items(), key=lambda x: x[1].get('win_rate', 0), reverse=True)[:3]
        if best_hours:
            hour_list = ', '.join([f"{h[0]}:00 ({h[1]['win_rate']:.0f}% WR)" for h in best_hours])
            msg += f"Best Hours: {hour_list}\n"

    return msg


def format_learning_report():
    """Format learning insights for Telegram (enhanced with recommendations)."""
    learning = learn_from_trades()

    if not learning['signals']:
        return "Learning: No trades yet to analyze"

    msg = "LEARNING INSIGHTS\n"
    msg += "=" * 50 + "\n\n"

    # Top signals
    enabled_sigs = {k: v for k, v in learning['signals'].items() if v['enabled']}
    if enabled_sigs:
        msg += "Enabled Signals (High Confidence):\n"
        for sig, data in sorted(enabled_sigs.items(), key=lambda x: x[1]['confidence'], reverse=True)[:5]:
            msg += f"  {sig}: {data['total']} trades, WR {data['win_rate']:.0f}% "
            msg += f"(conf {data['confidence']:.0f}/100)\n"

    # Disabled signals
    disabled_sigs = {k: v for k, v in learning['signals'].items() if not v['enabled']}
    if disabled_sigs:
        msg += "\nDisabled Signals (Low WR):\n"
        for sig, data in sorted(disabled_sigs.items(), key=lambda x: x[1]['win_rate'])[:3]:
            msg += f"  {sig}: WR {data['win_rate']:.0f}% ({data['wins']}W-{data['losses']}L) — Too risky\n"

    # Symbol performance
    if learning['symbols']:
        msg += "\nSymbol Performance:\n"
        for sym, data in sorted(learning['symbols'].items(), key=lambda x: x[1]['win_rate'], reverse=True):
            msg += f"  {sym}: {data['total']} trades, WR {data['win_rate']:.0f}%, P&L ${data['total_pnl']:.2f}\n"

    # Auto-recommendations
    recs = generate_recommendations()
    if recs:
        msg += "\n" + recs

    return msg


def get_enabled_signals():
    """Get list of enabled signals (for alert filtering)."""
    learning = load_learning()
    enabled = [sig for sig, data in learning['signals'].items() if data['enabled']]
    return enabled if enabled else list(learning['signals'].keys())


def get_top_signals(limit=3):
    """Get top N signals by win rate (for quality filtering).

    Only return signals with at least MIN_TRADES_PER_SIGNAL trades.
    """
    learning = learn_from_trades()  # Update data first

    if not learning['signals']:
        return []

    # Filter signals with enough data + enabled
    valid_signals = {sig: data for sig, data in learning['signals'].items()
                     if data['total'] >= MIN_TRADES_PER_SIGNAL and data['enabled']}

    if not valid_signals:
        return list(learning['signals'].keys())[:limit]  # Fallback to any signals

    # Sort by win rate descending
    sorted_signals = sorted(valid_signals.items(),
                           key=lambda x: x[1]['win_rate'],
                           reverse=True)

    return [sig for sig, _ in sorted_signals[:limit]]


def get_signal_confidence(signal_name):
    """Get confidence score for a signal (0-100)."""
    learning = load_learning()
    if signal_name in learning['signals']:
        return learning['signals'][signal_name].get('confidence', 0)
    return 0


if __name__ == "__main__":
    learning = learn_from_trades()
    print(format_learning_report())
