# -*- coding: utf-8 -*-
"""Send trading alert via Telegram."""
import requests
import sys
from datetime import datetime

# Bot token + Chat ID
BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHAT_ID = "1085188912"  # Personal chat
CHANNEL_ID = "@Zion_XAU_Signals"  # Public channel
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def send_alert(symbol, entry, sl, tp, lot, reason=""):
    """Gửi alert setup qua Telegram.

    Args:
        symbol: "XAU", "BTC", etc.
        entry: entry price
        sl: stop loss
        tp: take profit target (hoặc "500-600" string)
        lot: lot size
        reason: tại sao setup (Dow, MA34/89, etc.)
    """
    message = f"""
🎯 TRADE SIGNAL - {symbol}

📍 **Entry:** ${entry:,.2f}
🛑 **SL:** ${sl:,.2f}
🎁 **TP:** ${tp}

📦 **Lot:** {lot}
⏰ **Time:** {datetime.now().strftime('%H:%M UTC')}

💡 **Reason:** {reason}

---
Status: READY TO TRADE
"""

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[OK] Alert sent to Telegram: {symbol}")
        else:
            print(f"[ERROR] Telegram error: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Failed to send alert: {e}")


def send_text(text):
    """Gửi raw text message."""
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    # CLI usage:
    # python send_alert.py XAU 4560 4570 "4540-4530" 0.2 "Dow DOWN + MA BEARISH" --channel
    if len(sys.argv) < 5:
        print("Usage: python send_alert.py SYMBOL ENTRY SL TP LOT [REASON] [--channel]")
        print("  --channel: send to @Zion_XAU_Signals (public), else personal chat")
        print("Example: python send_alert.py XAU 4560 4570 4540-4530 0.2 'Dow DOWN' --channel")
        sys.exit(1)

    symbol = sys.argv[1]
    entry = float(sys.argv[2])
    sl = float(sys.argv[3])
    tp = sys.argv[4]
    lot = float(sys.argv[5])

    # Check if --channel flag present
    use_channel = "--channel" in sys.argv
    if use_channel:
        reason = " ".join(sys.argv[6:-1]) if len(sys.argv) > 7 else "Setup Signal"
        globals()['CHAT_ID'] = CHANNEL_ID
    else:
        reason = " ".join(sys.argv[6:]) if len(sys.argv) > 6 else "Setup Signal"

    send_alert(symbol, entry, sl, tp, lot, reason)
