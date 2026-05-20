# -*- coding: utf-8 -*-
"""Session management: detect trading sessions, smart filtering, auto-learn best hours."""
from datetime import datetime
import json
from pathlib import Path

SESSIONS_FILE = "sessions.json"


def get_current_session(hour_utc):
    """Get current trading session from UTC hour.

    Returns: {'session': 'ASIAN'/'EUROPEAN'/'AMERICAN'/'OVERLAP', 'hour_utc': hour, 'description': str}
    """
    # UTC times (approximate)
    if 6 <= hour_utc < 8:
        return {'session': 'ASIAN', 'hour_utc': hour_utc, 'description': 'Tokyo/Singapore (quiet)', 'volatility': 'LOW'}
    elif 8 <= hour_utc < 14:
        return {'session': 'ASIAN_EUROPEAN_OVERLAP', 'hour_utc': hour_utc, 'description': 'Tokyo/London overlap', 'volatility': 'MEDIUM'}
    elif 14 <= hour_utc < 16:
        return {'session': 'EUROPEAN_AMERICAN_OVERLAP', 'hour_utc': hour_utc, 'description': 'London/New York overlap', 'volatility': 'HIGH'}
    elif 16 <= hour_utc < 22:
        return {'session': 'AMERICAN', 'hour_utc': hour_utc, 'description': 'New York (very active)', 'volatility': 'VERY_HIGH'}
    else:  # 22-6
        return {'session': 'OVERNIGHT', 'hour_utc': hour_utc, 'description': 'Quiet overnight', 'volatility': 'VERY_LOW'}


def load_session_data():
    """Load hourly win rate data."""
    if Path(SESSIONS_FILE).exists():
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'hours': {str(h): {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'win_rate': 0} for h in range(24)},
        'sessions': {},
        'best_hours': [],
        'last_update': None
    }


def save_session_data(data):
    """Save hourly win rate data."""
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def should_skip_session(hour_utc, signal_confidence):
    """Determine if should skip alert based on session + confidence.

    Option C Logic:
    - Asian (6-8 UTC): skip unless confidence >= 75 (very beautiful)
    - Asian-Euro overlap (8-14 UTC): always post (>= 50)
    - Euro-American overlap (14-16 UTC): always post (>= 50)
    - American (16-22 UTC): always post (>= 50)
    - Overnight (22-6 UTC): skip (dead time)

    Option D Logic:
    - If hourly data available: skip if win_rate < 45%
    - If signal_confidence >= 75: override and post anyway (beautiful setup)
    """
    session_info = get_current_session(hour_utc)
    session = session_info['session']

    # Load hourly stats
    session_data = load_session_data()
    hour_stats = session_data['hours'].get(str(hour_utc), {})
    hour_win_rate = hour_stats.get('win_rate', 50)

    # Option C: Session-based filtering
    if session == 'ASIAN':
        # Skip Asian unless beautiful signal (conf >= 75)
        if signal_confidence >= 75:
            return False, "Beautiful Asian signal (conf 75+), post anyway"
        else:
            return True, f"Asian session quiet, skip (need conf >=75, have {signal_confidence:.0f})"

    elif session == 'OVERNIGHT':
        # Always skip overnight
        if signal_confidence >= 80:  # Super rare, very high confidence
            return False, "Extreme overnight signal (conf 80+), post anyway"
        else:
            return True, "Overnight dead time, skip"

    # Option D: Auto-learned hourly filtering
    # If we have enough data on this hour, check win rate
    if hour_stats.get('trades', 0) >= 5:
        if hour_win_rate < 45:
            # Low win rate hour, skip unless super confident
            if signal_confidence >= 80:
                return False, f"Low win hour ({hour_win_rate:.0f}% WR) but extreme signal (conf 80+)"
            else:
                return True, f"Bad hour ({hour_win_rate:.0f}% WR), skip"
        elif hour_win_rate >= 70:
            # Best hour, lower threshold
            if signal_confidence >= 40:  # Lower bar during best hours
                return False, f"Premium hour ({hour_win_rate:.0f}% WR), post with lower threshold"

    # Default: post (normal threshold >=50 checked elsewhere)
    return False, "Normal trading hour, proceed with normal filters"


def update_hourly_stats(hour_utc, pnl):
    """Update win rate for a specific hour after trade closes."""
    session_data = load_session_data()
    hour_key = str(hour_utc)

    if hour_key not in session_data['hours']:
        session_data['hours'][hour_key] = {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'win_rate': 0}

    hour_data = session_data['hours'][hour_key]
    hour_data['trades'] += 1
    hour_data['pnl'] += pnl

    if pnl > 0:
        hour_data['wins'] += 1
    else:
        hour_data['losses'] += 1

    # Recalculate win rate
    if hour_data['trades'] > 0:
        hour_data['win_rate'] = (hour_data['wins'] / hour_data['trades']) * 100

    session_data['last_update'] = datetime.now().isoformat()
    save_session_data(session_data)


def get_best_trading_hours():
    """Get top hours by win rate."""
    session_data = load_session_data()

    # Filter hours with enough trades
    valid_hours = {h: data for h, data in session_data['hours'].items()
                   if data['trades'] >= 5}

    if not valid_hours:
        return []

    # Sort by win rate descending
    sorted_hours = sorted(valid_hours.items(),
                         key=lambda x: x[1]['win_rate'],
                         reverse=True)

    return [{'hour': int(h), 'win_rate': data['win_rate'], 'trades': data['trades']}
            for h, data in sorted_hours[:5]]


def format_session_recommendations():
    """Format session analysis for Telegram."""
    session_data = load_session_data()

    msg = "SESSION ANALYSIS (Hourly WR):\n"
    msg += "=" * 40 + "\n"

    best_hours = get_best_trading_hours()
    if best_hours:
        msg += "Best Trading Hours:\n"
        for h in best_hours:
            msg += f"  {h['hour']:02d}:00 UTC → {h['win_rate']:.0f}% WR ({h['trades']} trades)\n"

    # Worst hours
    valid_hours = {h: data for h, data in session_data['hours'].items()
                   if data['trades'] >= 5}
    if valid_hours:
        sorted_hours = sorted(valid_hours.items(),
                             key=lambda x: x[1]['win_rate'])
        msg += "\nWorst Hours (skip if possible):\n"
        for h, data in sorted_hours[:3]:
            msg += f"  {int(h):02d}:00 UTC → {data['win_rate']:.0f}% WR ({data['trades']} trades)\n"

    return msg


if __name__ == "__main__":
    # Test
    print("Hour 8 (Asia-Euro overlap):", get_current_session(8))
    print("Hour 15 (Euro-American):", get_current_session(15))
    print("Hour 20 (American):", get_current_session(20))

    skip, reason = should_skip_session(7, 72)  # Asian, medium conf
    print(f"Hour 7, conf 72: skip={skip}, reason={reason}")

    skip, reason = should_skip_session(7, 80)  # Asian, high conf
    print(f"Hour 7, conf 80: skip={skip}, reason={reason}")
