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
        'seed_trades': [],   # data backtest bơm vào (python backtest.py --seed)
        'last_update': None,
        'disabled_signals': []
    }


def save_learning(data):
    """Save learning data."""
    with open(LEARNING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _pair_key(signal, symbol):
    """Key học theo CẶP signal@symbol — XAU ($10/pip) và BTC ($0.01/pip) scale P&L
    khác nhau, gộp chung 1 rổ làm méo avg_win/RRR."""
    return f"{signal}@{symbol}"


def _gather_trades(learning=None):
    """Gộp mọi nguồn lệnh ĐÃ ĐÓNG về 1 format chung cho learning.

    Nguồn (Phase 10.2 — trước đây chỉ đọc trades.json nên hệ SMC đóng lệnh
    vào alert_tracker.json mà learning KHÔNG BAO GIỜ thấy → bot học 0 lệnh):
      1. alert_tracker.json — lệnh SMC live (watchdog auto-close + /tp /sl /exit)
      2. trades.json — hệ /enter /close cũ (legacy)
      3. learning.json['seed_trades'] — kết quả backtest (fix cold-start)

    Format chung: {'signal', 'symbol', 'pnl', 'entry_time', 'source': 'live'|'seed'}
    EXPIRED không tính (pnl 0, không phải win/loss).
    """
    trades = []

    # 1. Lệnh SMC live từ alert tracker (nguồn chính hiện tại)
    try:
        from trade_tracker import load_tracker
        for a in load_tracker().get('closed_trades', []):
            if a.get('result') not in ('WIN', 'LOSS'):
                continue  # EXPIRED — không làm bẩn win rate
            trades.append({
                'signal': a.get('signal', 'UNKNOWN'),
                'symbol': a.get('symbol', 'XAU'),
                'pnl': a.get('pnl', 0),
                'entry_time': a.get('posted_at', ''),
                'source': 'live',
            })
    except Exception:
        pass

    # 2. Legacy trades.json (hệ /enter /close cũ)
    for t in load_trades():
        if t.get('status') != 'CLOSED':
            continue
        trades.append({
            'signal': t.get('signal', 'UNKNOWN'),
            'symbol': t.get('symbol', 'XAU'),
            'pnl': t.get('pnl', 0),
            'entry_time': t.get('entry_time', ''),
            'source': 'live',
        })

    # 3. Backtest seed (đã lưu sẵn trong learning.json)
    if learning is None:
        learning = load_learning()
    for t in learning.get('seed_trades', []):
        trades.append({
            'signal': t.get('signal', 'UNKNOWN'),
            'symbol': t.get('symbol', 'XAU'),
            'pnl': t.get('pnl', 0),
            'entry_time': t.get('entry_time', ''),
            'source': 'seed',
        })

    # Sort theo thời gian để "5 lệnh gần nhất" (consistency) đúng thứ tự
    trades.sort(key=lambda t: t.get('entry_time') or '')
    return trades


def learn_from_trades():
    """Analyze all trades, extract patterns, update learning database.

    Phase 10.2:
    - Đọc từ MỌI nguồn (_gather_trades) — trước đây chỉ đọc trades.json rỗng
      nên learning chết lâm sàng, bot bootstrap vĩnh viễn với conf 0%.
    - Học theo CẶP signal@symbol (vd 'BUY_SMC_OB@XAU') — hết méo avg_win/RRR
      do trộn scale P&L XAU/BTC.
    """
    learning = load_learning()
    closed_trades = _gather_trades(learning)

    if not closed_trades:
        return learning

    # Reset signals data (recalculate from trades)
    learning['signals'] = {}

    # Analyze per-pair (signal@symbol)
    for trade in closed_trades:
        key = _pair_key(trade['signal'], trade['symbol'])
        is_win = trade['pnl'] > 0

        if key not in learning['signals']:
            learning['signals'][key] = {
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
                'live': 0,        # số lệnh thật
                'seed': 0,        # số lệnh backtest seed
                'last_trade': None
            }

        sig_data = learning['signals'][key]
        sig_data['total'] += 1
        sig_data['total_pnl'] += trade['pnl']
        sig_data['last_trade'] = trade['entry_time']
        sig_data['seed' if trade.get('source') == 'seed' else 'live'] += 1

        if is_win:
            sig_data['wins'] += 1
        else:
            sig_data['losses'] += 1

    # Calculate stats per pair
    for key, data in learning['signals'].items():
        if data['total'] > 0:
            data['win_rate'] = (data['wins'] / data['total']) * 100

        # Only evaluate if enough trades
        if data['total'] >= MIN_TRADES_PER_SIGNAL:
            key_trades = [t for t in closed_trades
                          if _pair_key(t['signal'], t['symbol']) == key]
            wins = [t for t in key_trades if t['pnl'] > 0]
            losses = [t for t in key_trades if t['pnl'] < 0]

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

            # Consistency: check recent trades (đã sort theo thời gian trong _gather_trades)
            recent = key_trades[-5:]
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

    # Analyze per-symbol — CHỈ lệnh live (seed backtest sẽ thổi phồng số liệu thật)
    learning['symbols'] = {}
    for trade in closed_trades:
        if trade.get('source') == 'seed':
            continue
        sym = trade.get('symbol', 'XAU')
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
    learning = load_learning()
    closed_trades = _gather_trades(learning)

    if not closed_trades:
        return {}

    patterns = {
        'h1_trends': {},  # H1=UP/DOWN/NEUTRAL: win rate
        'volume_levels': {},  # volume_ratio: win rate
        'hours': {},  # hour of day: win rate
        'symbols': {},  # per symbol: top signals
        'recommendations': []
    }

    # Per-pair recommendation (key = signal@symbol)
    for key in learning['signals'].keys():
        key_trades = [t for t in closed_trades
                      if _pair_key(t['signal'], t['symbol']) == key]
        if len(key_trades) >= 5:
            wr = sum(1 for t in key_trades if t['pnl'] > 0) / len(key_trades) * 100

            # Recommendation logic
            if wr >= 65:
                patterns['recommendations'].append(f"KEEP {key}: {wr:.0f}% WR (high confidence)")
            elif wr <= 35:
                patterns['recommendations'].append(f"DISABLE {key}: {wr:.0f}% WR (too risky)")
            elif wr >= 50:
                patterns['recommendations'].append(f"WATCH {key}: {wr:.0f}% WR (neutral, test more)")

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

    msg = "LEARNING INSIGHTS (theo cặp signal@symbol)\n"
    msg += "=" * 50 + "\n\n"

    # Top signals
    enabled_sigs = {k: v for k, v in learning['signals'].items() if v['enabled']}
    if enabled_sigs:
        msg += "Enabled Signals (High Confidence):\n"
        for sig, data in sorted(enabled_sigs.items(), key=lambda x: x[1]['confidence'], reverse=True)[:5]:
            src = f"{data.get('live', 0)} live"
            if data.get('seed', 0):
                src += f" + {data['seed']} backtest"
            msg += f"  {sig}: {data['total']} trades ({src}), WR {data['win_rate']:.0f}% "
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
        # KHÔNG fallback bừa sang signal chưa đủ data (dính BUY_TEST → bot câm).
        # Trả [] để smart_alert_loop kích hoạt bootstrap DEFAULT_SIGNALS.
        return []

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
