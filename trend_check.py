# -*- coding: utf-8 -*-
"""Check trend for 6 symbols."""
import requests
from fetch import fetch_symbol
from indicators import IndicatorSet
from analyze import Analysis
from datetime import datetime

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHANNEL_ID = "@Zion_XAU_Signals"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def check_trends():
    """Fetch + analyze trends."""
    symbols = ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]

    lines = [f"📊 **TREND CHECK** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "1d", 60)
            ind = IndicatorSet(df).calculate_all()
            analysis = Analysis(ind, sym, "1d")
            summary = analysis.summary()

            trend = summary['trend']
            momentum = summary['momentum']
            close = summary['close']

            trend_emoji = "📈" if trend['direction'] == "UP" else "📉" if trend['direction'] == "DOWN" else "➡️"
            mom_emoji = "🔥" if momentum['level'] == "STRONG" else "⚡" if momentum['level'] == "MODERATE" else "❄️"

            lines.append(f"{trend_emoji} **{sym}** @ ${close:,.2f}")
            lines.append(f"  Trend: {trend['direction']} ({trend['strength']}/10) | Momentum: {momentum['level']} (RSI {momentum['rsi']})")
        except Exception as e:
            lines.append(f"**{sym}:** ERROR")

    message = "\n".join(lines)
    return message


def send_trend_check():
    """Send trend check to channel."""
    message = check_trends()
    print(message)

    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        if resp.status_code == 200:
            print("\n✅ Trend check sent to channel")
        else:
            print(f"❌ Error: {resp.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    send_trend_check()
