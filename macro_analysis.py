# -*- coding: utf-8 -*-
"""Macro economic analysis & daily report."""
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

MACRO_FILE = "macro_calendar.json"

# Economic calendar API (using free tier)
CALENDAR_API = "https://www.fxmarketapi.com/v1/calendar"

# Event importance levels
CRITICAL_EVENTS = ['CPI', 'Non-Farm Payroll', 'NFP', 'FOMC', 'GDP', 'Inflation', 'Interest Rate']
HIGH_EVENTS = ['Unemployment', 'Retail Sales', 'Consumer Confidence', 'Manufacturing PMI', 'Services PMI']
MEDIUM_EVENTS = ['Employment', 'PPI', 'Housing Starts', 'Building Permits']


def get_event_importance(event_name):
    """Classify event importance."""
    event_upper = event_name.upper()

    for critical in CRITICAL_EVENTS:
        if critical.upper() in event_upper:
            return "🔴 CRITICAL"

    for high in HIGH_EVENTS:
        if high.upper() in event_upper:
            return "⚠️ HIGH"

    for medium in MEDIUM_EVENTS:
        if medium.upper() in event_upper:
            return "◐ MEDIUM"

    return "◯ LOW"


def fetch_economic_calendar(days_ahead=1):
    """Fetch economic calendar for next N days.

    Returns: list of events sorted by time
    """
    try:
        # Build calendar manually (since free API limited)
        # In production, use https://www.tradingeconomics.com/calendar
        calendar = get_hardcoded_calendar(days_ahead)
        return calendar
    except Exception as e:
        print(f"Error fetching calendar: {e}")
        return []


def get_hardcoded_calendar(days_ahead=1):
    """Hardcoded calendar for demo (replace with API later)."""
    today = datetime.utcnow()
    target_date = today + timedelta(days=days_ahead)

    # Sample events (in production, fetch from TradingEconomics API)
    sample_events = [
        {
            'time': '13:30 UTC',
            'country': 'UK',
            'event': 'CPI YoY',
            'importance': get_event_importance('CPI'),
            'forecast': '2.8%',
            'previous': '3.0%',
            'time_unix': 1234567890
        },
        {
            'time': '20:00 UTC',
            'country': 'US',
            'event': 'PPI MoM',
            'importance': get_event_importance('PPI'),
            'forecast': '+0.2%',
            'previous': '+0.1%',
            'time_unix': 1234567890
        },
    ]

    return sample_events


def generate_daily_report(days_ahead=0):
    """Generate daily macro report.

    Args:
        days_ahead: 0=today, 1=tomorrow

    Returns: formatted report string
    """
    target_date = datetime.utcnow() + timedelta(days=days_ahead)
    date_str = target_date.strftime('%Y-%m-%d')

    msg = f"📊 MACRO REPORT — {date_str}\n"
    msg += "=" * 40 + "\n\n"

    # Yesterday recap (simplified)
    msg += "🔙 YESTERDAY RECAP:\n"
    msg += "• US CPI +0.4% (expect +0.3%) → USD pump, XAU -$20\n"
    msg += "• Fed speaker comments: dovish tone\n"
    msg += "• Market reaction: Risk-on, equities +1.2%\n\n"

    # Today's calendar
    msg += "📅 TODAY'S ECONOMIC CALENDAR:\n"
    calendar = fetch_economic_calendar(days_ahead)

    if calendar:
        for event in calendar:
            msg += f"{event['time']} {event['importance']}\n"
            msg += f"  {event['country']} {event['event']}\n"
            msg += f"  Forecast: {event['forecast']} | Previous: {event['previous']}\n"
    else:
        msg += "  (Calendar data loading...)\n"

    msg += "\n"

    # Trading implications
    msg += "💡 TRADING IMPLICATIONS:\n"
    msg += "• CPI data critical for USD direction\n"
    msg += "• If CPI > forecast → USD strength → XAU pressure\n"
    msg += "• Avoid tight stops during data release (±5 pips)\n"
    msg += "• Best entries: 1h after data release (volatility settles)\n\n"

    # Risk warning
    msg += "⚠️ RISK ALERT:\n"
    msg += "• High volatility expected\n"
    msg += "• Widen stop loss by 50% today\n"
    msg += "• Avoid counter-trend entries near data release\n\n"

    msg += "Good luck! 🚀\n"

    return msg


def generate_pre_event_alert(event_name, forecast, previous, minutes_until=30):
    """Generate pre-event alert (alert sent 30min before event).

    Args:
        event_name: event name (CPI, NFP, etc.)
        forecast: expected value
        previous: previous value
        minutes_until: minutes until event

    Returns: alert message
    """
    msg = f"⏰ EVENT ALERT — {minutes_until} minutes until {event_name}\n"
    msg += "=" * 40 + "\n\n"

    msg += f"📊 {event_name}\n"
    msg += f"Forecast: {forecast}\n"
    msg += f"Previous: {previous}\n\n"

    # Quick analysis
    msg += "⚡ QUICK ANALYSIS:\n"

    if 'CPI' in event_name or 'Inflation' in event_name:
        msg += "• CPI is CRITICAL for USD strength\n"
        msg += f"• If actual > {forecast} → USD UP → XAU DOWN\n"
        msg += "• If actual < forecast → USD weak → XAU UP\n"
        msg += "• Expected move: 50-100 pips in USD/JPY\n"

    elif 'NFP' in event_name or 'Payroll' in event_name:
        msg += "• NFP impacts USD and risk sentiment\n"
        msg += "• Strong jobs → Fed hawkish → USD UP, gold DOWN\n"
        msg += "• Weak jobs → Flight to safety → USD mixed, gold UP\n"
        msg += "• Expected move: 100-200 pips volatility\n"

    elif 'PPI' in event_name:
        msg += "• PPI (inflation) drives rate expectations\n"
        msg += "• Higher PPI → USD hawkish → XAU pressure\n"
        msg += "• Expected move: 30-50 pips\n"

    msg += "\n💼 TRADING STRATEGY:\n"
    msg += "• Set wider stops (±10 pips minimum)\n"
    msg += "• Avoid NEW entries 15min before → 15min after\n"
    msg += "• If already IN: trail stops or move to breakeven\n"
    msg += "• BEST: Enter 1-2h AFTER data, when volatility settles\n\n"

    msg += "Stay safe! 🛡️\n"

    return msg


def format_macro_summary():
    """Quick summary for /macro command."""
    msg = "📊 MACRO SUMMARY\n"
    msg += "Daily reports: 1 AM US time\n"
    msg += "Pre-event alerts: 30 min before major events\n"
    msg += "High impact events: CPI, NFP, FOMC, GDP\n"
    msg += "\nMonitor economic calendar for trading opportunities!\n"
    return msg


if __name__ == "__main__":
    # Test
    print(generate_daily_report(0))
    print("\n" + "="*50 + "\n")
    print(generate_pre_event_alert("US CPI", "+0.4%", "+0.3%", 30))
    print("\n" + "="*50 + "\n")
    print(format_macro_summary())
