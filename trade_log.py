# -*- coding: utf-8 -*-
"""Trade journal + P&L tracking."""
import json
from datetime import datetime
from pathlib import Path

TRADE_FILE = "trades.json"


def load_trades():
    """Load trades from JSON file."""
    if Path(TRADE_FILE).exists():
        with open(TRADE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_trades(trades):
    """Save trades to JSON file."""
    with open(TRADE_FILE, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)


def log_entry(signal_name, entry_price, lot=0.2):
    """Log trade entry.

    Args:
        signal_name: e.g. 'BUY_PIVOT_S1_BOUNCE'
        entry_price: entry price
        lot: position size (default 0.2)

    Returns:
        trade dict with entry details
    """
    trade = {
        'id': len(load_trades()) + 1,
        'signal': signal_name,
        'entry_price': entry_price,
        'entry_time': datetime.now().isoformat(),
        'lot': lot,
        'exit_price': None,
        'exit_time': None,
        'pnl': None,
        'pnl_pips': None,
        'status': 'OPEN'
    }

    trades = load_trades()
    trades.append(trade)
    save_trades(trades)

    return trade


def close_trade(trade_id, exit_price):
    """Close trade with exit price.

    Args:
        trade_id: trade ID
        exit_price: exit price

    Returns:
        updated trade dict
    """
    trades = load_trades()

    for trade in trades:
        if trade['id'] == trade_id:
            trade['exit_price'] = exit_price
            trade['exit_time'] = datetime.now().isoformat()
            trade['status'] = 'CLOSED'

            # Calculate P&L
            # For XAU: P&L = (exit - entry) * $10 * lot
            # Example: 100 pips (100 price units) * 0.2 lot = 100 * 10 * 0.2 = $200
            pips = exit_price - trade['entry_price']
            trade['pnl_pips'] = pips
            trade['pnl'] = pips * 10 * trade['lot']

            save_trades(trades)
            return trade

    return None


def get_stats():
    """Calculate aggregate stats."""
    trades = load_trades()

    if not trades:
        return {
            'total_trades': 0,
            'closed_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'rrr': 0,
            'total_pnl': 0,
            'by_signal': {}
        }

    closed = [t for t in trades if t['status'] == 'CLOSED']
    wins = [t for t in closed if t['pnl'] > 0]
    losses = [t for t in closed if t['pnl'] < 0]

    total_pnl = sum(t['pnl'] for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(abs(t['pnl']) for t in losses) / len(losses) if losses else 0
    rrr = avg_win / avg_loss if avg_loss > 0 else 0

    # Stats by signal
    by_signal = {}
    for trade in closed:
        sig = trade['signal']
        if sig not in by_signal:
            by_signal[sig] = {'wins': 0, 'losses': 0, 'total_pnl': 0}

        if trade['pnl'] > 0:
            by_signal[sig]['wins'] += 1
        else:
            by_signal[sig]['losses'] += 1
        by_signal[sig]['total_pnl'] += trade['pnl']

    return {
        'total_trades': len(trades),
        'closed_trades': len(closed),
        'open_trades': len([t for t in trades if t['status'] == 'OPEN']),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'rrr': rrr,
        'total_pnl': total_pnl,
        'by_signal': by_signal
    }


def format_stats():
    """Format stats for Telegram output."""
    stats = get_stats()

    if stats['closed_trades'] == 0:
        return "No closed trades yet"

    msg = "TRADE STATS\n"
    msg += f"Total: {stats['total_trades']} | Open: {stats['open_trades']} | Closed: {stats['closed_trades']}\n"
    msg += f"Win Rate: {stats['win_rate']:.1f}% | RRR: {stats['rrr']:.2f}\n"
    msg += f"Avg Win: ${stats['avg_win']:.2f} | Avg Loss: ${stats['avg_loss']:.2f}\n"
    msg += f"Total P&L: ${stats['total_pnl']:.2f}\n"
    msg += "\nBy Signal:\n"

    for sig, data in sorted(stats['by_signal'].items()):
        wr = data['wins'] / (data['wins'] + data['losses']) * 100 if (data['wins'] + data['losses']) > 0 else 0
        msg += f"  {sig}: {data['wins']}W-{data['losses']}L ({wr:.0f}%) | P&L: ${data['total_pnl']:.2f}\n"

    return msg


def list_trades(limit=10):
    """List recent trades."""
    trades = load_trades()
    recent = trades[-limit:]

    if not recent:
        return "No trades logged"

    msg = "RECENT TRADES\n"
    for t in recent:
        status = "OPEN" if t['status'] == 'OPEN' else f"${t['pnl']:.2f}"
        msg += f"#{t['id']} {t['signal']}: {t['entry_price']:.2f} -> {t['exit_price'] or '?'} [{status}]\n"

    return msg


def get_daily_stats(date_str=None):
    """Get stats for specific date (YYYY-MM-DD). Default: today."""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')

    trades = load_trades()
    daily_trades = [t for t in trades if t['entry_time'].startswith(date_str)]

    if not daily_trades:
        return None

    closed = [t for t in daily_trades if t['status'] == 'CLOSED']
    if not closed:
        return None

    wins = [t for t in closed if t['pnl'] > 0]
    losses = [t for t in closed if t['pnl'] < 0]

    total_pnl = sum(t['pnl'] for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(abs(t['pnl']) for t in losses) / len(losses) if losses else 0

    by_signal = {}
    for trade in closed:
        sig = trade['signal']
        if sig not in by_signal:
            by_signal[sig] = {'wins': 0, 'losses': 0, 'total_pnl': 0}
        if trade['pnl'] > 0:
            by_signal[sig]['wins'] += 1
        else:
            by_signal[sig]['losses'] += 1
        by_signal[sig]['total_pnl'] += trade['pnl']

    return {
        'date': date_str,
        'total_closed': len(closed),
        'total_open': len([t for t in daily_trades if t['status'] == 'OPEN']),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_pnl': total_pnl,
        'by_signal': by_signal
    }


def format_daily_stats():
    """Format today's stats for daily report."""
    daily = get_daily_stats()

    if not daily or daily['total_closed'] == 0:
        return "📊 DAILY REPORT — No trades closed today"

    msg = f"📊 DAILY REPORT — {daily['date']}\n"
    msg += f"Closed: {daily['total_closed']} | Open: {daily['total_open']}\n"
    msg += f"Wins: {daily['wins']} | Losses: {daily['losses']} | WR: {daily['win_rate']:.1f}%\n"
    msg += f"P&L: ${daily['total_pnl']:.2f}\n"

    if daily['by_signal']:
        msg += "\nBy Signal:\n"
        for sig, data in sorted(daily['by_signal'].items()):
            wr = data['wins'] / (data['wins'] + data['losses']) * 100 if (data['wins'] + data['losses']) > 0 else 0
            msg += f"  {sig}: {data['wins']}W-{data['losses']}L ({wr:.0f}%) | ${data['total_pnl']:.2f}\n"

    return msg


if __name__ == "__main__":
    # Test
    log_entry("BUY_PIVOT_S1_BOUNCE", 4550.00)
    log_entry("SELL_RESISTANCE_BREAK", 4560.00)
    close_trade(1, 4560.00)

    print(format_stats())
    print("\n" + list_trades())
