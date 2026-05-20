# -*- coding: utf-8 -*-
"""Check current prices for 6 symbols."""
import requests
from fetch import fetch_symbol
from datetime import datetime

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHANNEL_ID = "@Zion_XAU_Signals"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def check_prices():
    """Fetch + display prices."""
    symbols = ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]

    lines = [f"💹 **PRICE CHECK** — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in symbols:
        try:
            df = fetch_symbol(sym, "1d", 1)
            close = df['Close'].iloc[-1]
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]

            lines.append(f"**{sym}:** ${close:,.2f}")
            lines.append(f"  High: ${high:,.2f} | Low: ${low:,.2f}")
        except Exception as e:
            lines.append(f"**{sym}:** ERROR - {e}")

    message = "\n".join(lines)
    return message


def send_price_check():
    """Send price check to channel."""
    message = check_prices()
    print(message)

    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        if resp.status_code == 200:
            print("\n✅ Price check sent to channel")
        else:
            print(f"❌ Error: {resp.text}")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    send_price_check()
