# -*- coding: utf-8 -*-
"""Track posted alerts, monitor TP/SL, auto-learn from live results."""
import json
from pathlib import Path
from datetime import datetime, timedelta

TRACKER_FILE = "alert_tracker.json"

# Risk per pip for each symbol (in dollars per pip)
RISK_PER_PIP = {
    'XAU': 10,      # Gold: $10/pip
    'XAG': 0.5,     # Silver: $0.50/pip
    'BTC': 0.01,    # Bitcoin
    'ETH': 0.01,    # Ethereum
    'USOIL': 0.1,   # Crude Oil
    'DXY': 0.1      # Dollar Index
}


def get_risk_per_pip(symbol):
    """Get risk per pip for symbol (default XAU if unknown)."""
    return RISK_PER_PIP.get(symbol, 10)


def load_tracker():
    """Load alert tracking data."""
    if Path(TRACKER_FILE).exists():
        with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'posted_alerts': [],  # Currently active/pending alerts
        'closed_trades': [],  # Closed trades with TP/SL results
        'session_limits': {},  # Track alerts per session today
        'last_update': None
    }


def save_tracker(data):
    """Save tracking data."""
    with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def post_alert(symbol, timeframe, signal, entry, sl, tp, h1_trend, confidence, session, tp1=None, tp3=None):
    """Record a posted alert.

    Args:
        tp1: TP1 (127.2% extension for Fibo, optional)
        tp3: TP3 (200% extension for Fibo, optional)
    """
    tracker = load_tracker()

    # ID = max của cả pending + closed (trước đây đếm len(pending)+1 → one-at-a-time
    # làm pending luôn rỗng lúc post → mọi alert đều là #1)
    all_ids = ([a.get('id', 0) for a in tracker['posted_alerts']] +
               [a.get('id', 0) for a in tracker['closed_trades']])
    alert = {
        'id': (max(all_ids) + 1) if all_ids else 1,
        'symbol': symbol,
        'timeframe': timeframe,
        'signal': signal,
        'entry': entry,
        'sl': sl,
        'tp': tp,  # Primary TP (TP2 for Fibo, 2×ATR for ATR-based)
        'tp1': tp1,  # TP1 (127.2%) for Fibo only
        'tp3': tp3,  # TP3 (200%) for Fibo only
        'h1_trend': h1_trend,
        'confidence': confidence,
        'session': session,
        'posted_at': datetime.now().isoformat(),
        'status': 'PENDING',  # PENDING, TP_HIT, SL_HIT
        'result': None,  # 'WIN' or 'LOSS'
        'tp_level': None  # Which TP hit: 1, 2, or 3
    }

    tracker['posted_alerts'].append(alert)

    # Track per-session limit
    today = datetime.now().strftime('%Y-%m-%d')
    session_key = f"{today}_{session}"
    if session_key not in tracker['session_limits']:
        tracker['session_limits'][session_key] = 0
    tracker['session_limits'][session_key] += 1

    tracker['last_update'] = datetime.now().isoformat()
    save_tracker(tracker)

    return alert['id']


def close_alert(alert_id, result, exit_price=None, tp_level=None):
    """Mark alert as TP, SL, or manual exit.

    Args:
        alert_id: alert ID
        result: 'TP', 'SL', or 'EXIT'
        exit_price: actual exit price (for manual exits)
        tp_level: which TP hit (1, 2, or 3) - for TP result only
    """
    tracker = load_tracker()

    for alert in tracker['posted_alerts']:
        if alert['id'] == alert_id:
            symbol = alert.get('symbol', 'XAU')
            risk_per_pip = get_risk_per_pip(symbol)
            # SELL: lời khi giá GIẢM → nhân -1 (trước đây pnl SELL bị ngược dấu)
            side = -1 if 'SELL' in alert.get('signal', '') else 1

            if result == 'TP':
                alert['status'] = 'TP_HIT'
                alert['result'] = 'WIN'
                alert['tp_level'] = tp_level if tp_level else 2  # Default to TP2

                # Use appropriate TP level for exit price
                if tp_level == 1 and alert.get('tp1'):
                    alert['exit_price'] = alert['tp1']
                elif tp_level == 3 and alert.get('tp3'):
                    alert['exit_price'] = alert['tp3']
                else:
                    alert['exit_price'] = alert['tp']  # Default to TP2

                pnl = (alert['exit_price'] - alert['entry']) * risk_per_pip * side
            elif result == 'SL':
                alert['status'] = 'SL_HIT'
                alert['result'] = 'LOSS'
                alert['exit_price'] = alert['sl']
                pnl = (alert['sl'] - alert['entry']) * risk_per_pip * side
            elif result == 'EXIT' and exit_price is not None:
                # Manual exit at specific price
                alert['status'] = 'MANUAL_EXIT'
                alert['exit_price'] = exit_price
                pnl = (exit_price - alert['entry']) * risk_per_pip * side

                # Determine if WIN or LOSS based on profit
                if pnl > 0:
                    alert['result'] = 'WIN'
                else:
                    alert['result'] = 'LOSS'
            else:
                return None

            alert['pnl'] = pnl
            alert['closed_at'] = datetime.now().isoformat()

            # Cập nhật thống kê theo GIỜ post alert (session learning — trước đây
            # update_hourly_stats được import nhưng không ai gọi → sessions.json chết)
            try:
                from session_manager import update_hourly_stats
                hour_utc = datetime.fromisoformat(alert['posted_at']).hour
                update_hourly_stats(hour_utc, pnl)
            except Exception:
                pass  # thống kê giờ lỗi không được chặn việc đóng lệnh

            # Move to closed trades
            tracker['closed_trades'].append(alert)
            tracker['posted_alerts'].remove(alert)

            tracker['last_update'] = datetime.now().isoformat()
            save_tracker(tracker)

            return alert

    return None


def expire_alert(alert_id, reason="timeout"):
    """Đóng alert hết hạn — KHÔNG tính win/loss (pnl=0, không làm bẩn learning).

    Dùng khi giá không chạm SL/TP trong thời gian tối đa và user không xử lý tay.
    """
    tracker = load_tracker()
    for alert in tracker['posted_alerts']:
        if alert['id'] == alert_id:
            alert['status'] = 'EXPIRED'
            alert['result'] = None
            alert['pnl'] = 0
            alert['expire_reason'] = reason
            alert['closed_at'] = datetime.now().isoformat()
            tracker['closed_trades'].append(alert)
            tracker['posted_alerts'].remove(alert)
            tracker['last_update'] = datetime.now().isoformat()
            save_tracker(tracker)
            return alert
    return None


def get_pending_alerts():
    """Get currently pending alerts."""
    tracker = load_tracker()
    return tracker['posted_alerts']


def get_session_alert_count(session):
    """Get number of alerts posted in this session today."""
    tracker = load_tracker()
    today = datetime.now().strftime('%Y-%m-%d')
    session_key = f"{today}_{session}"
    return tracker['session_limits'].get(session_key, 0)


def has_open_trade():
    """Check if there's an open/pending trade."""
    tracker = load_tracker()
    return len(tracker['posted_alerts']) > 0


def get_signal_live_stats():
    """Get live win rate per signal from tracked trades."""
    tracker = load_tracker()

    if not tracker['closed_trades']:
        return {}

    stats = {}
    for trade in tracker['closed_trades']:
        if trade.get('result') not in ('WIN', 'LOSS'):
            continue  # EXPIRED alerts không tính vào win rate
        sig = trade['signal']
        if sig not in stats:
            stats[sig] = {'wins': 0, 'losses': 0, 'total': 0}

        stats[sig]['total'] += 1
        if trade['result'] == 'WIN':
            stats[sig]['wins'] += 1
        else:
            stats[sig]['losses'] += 1

    # Calculate win rates
    for sig, data in stats.items():
        if data['total'] > 0:
            data['win_rate'] = (data['wins'] / data['total']) * 100

    return stats


def format_tracker_status():
    """Format pending alerts status for logging."""
    pending = get_pending_alerts()

    if not pending:
        return "No open alerts"

    msg = f"PENDING ALERTS ({len(pending)} active):\n"
    for alert in pending:
        msg += f"  #{alert['id']} {alert['symbol']} {alert['signal']}: "
        msg += f"Entry {alert['entry']:.0f}, TP {alert['tp']:.0f}, SL {alert['sl']:.0f}\n"

    return msg


def format_live_performance():
    """Format live win rate from tracked trades."""
    stats = get_signal_live_stats()

    if not stats:
        return "No closed trades yet"

    msg = "LIVE PERFORMANCE (Tracked Alerts):\n"
    msg += "=" * 40 + "\n"

    for sig, data in sorted(stats.items(), key=lambda x: x[1]['win_rate'], reverse=True):
        msg += f"{sig}: {data['wins']}W-{data['losses']}L ({data['win_rate']:.0f}% WR)\n"

    return msg


if __name__ == "__main__":
    # Test
    alert_id = post_alert("XAU", "5m", "BUY_PIVOT_S1_BOUNCE", 4550, 4544, 4560, "UP", 75, "EUROPEAN")
    print(f"Posted alert #{alert_id}")

    print(format_tracker_status())

    close_alert(alert_id, "TP")
    print(f"Closed alert #{alert_id} with TP")

    print(format_live_performance())
