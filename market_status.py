# -*- coding: utf-8 -*-
"""Full market status — prices + trends + levels."""
import requests
from fetch import fetch_symbol
from indicators import IndicatorSet
from analyze import Analysis
from datetime import datetime

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHANNEL_ID = "@Zion_XAU_Signals"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def market_overview():
    """Full market overview."""
    symbols = ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]

    lines = [f"🌍 **MARKET STATUS** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "1d", 60)
            ind = IndicatorSet(df).calculate_all()
            analysis = Analysis(ind, sym, "1d")
            summary = analysis.summary()

            trend = summary['trend']
            momentum = summary['momentum']
            levels = summary['levels']
            close = summary['close']

            trend_emoji = "📈" if trend['direction'] == "UP" else "📉" if trend['direction'] == "DOWN" else "➡️"

            lines.append(f"{trend_emoji} **{sym}** ${close:,.2f}")
            lines.append(f"  Trend: {trend['direction']} | RSI: {momentum['rsi']} | R1: ${levels['resistance'][0]:,.2f} | S1: ${levels['support'][0]:,.2f}")
        except Exception as e:
            lines.append(f"**{sym}:** —")

    message = "\n".join(lines)
    return message


def send_market_status():
    """Send market status to channel."""
    message = market_overview()
    print(message)

    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        if resp.status_code == 200:
            print("\n✅ Market status sent to channel")
        else:
            print(f"❌ Error: {resp.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    send_market_status()
