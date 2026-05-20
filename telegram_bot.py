# -*- coding: utf-8 -*-
"""Telegram bot — listen /price /trend /status commands, reply."""
import requests
import time
from datetime import datetime

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = 0


def get_updates():
    """Poll for new messages."""
    global last_update_id
    try:
        url = f"{TELEGRAM_API}/getUpdates"
        payload = {"offset": last_update_id + 1, "timeout": 30}
        resp = requests.post(url, json=payload, timeout=35)
        data = resp.json()

        if data.get("ok"):
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"[ERROR] getUpdates: {e}")
        return []


def send_reply(chat_id, text):
    """Send message to chat."""
    try:
        url = f"{TELEGRAM_API}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[SENT] {len(text)} chars to {chat_id}")
            return True
        else:
            print(f"[FAIL] Status {resp.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] send_reply: {e}")
        return False


def handle_command(chat_id, text):
    """Handle /price or /trend command."""
    cmd = text.lower().strip()

    try:
        if "/price" in cmd:
            print(f"[PROCESS] /price for {chat_id}")
            from price_check import check_prices
            reply = check_prices()
            send_reply(chat_id, reply)

        elif "/trend" in cmd:
            print(f"[PROCESS] /trend for {chat_id}")
            from trend_check import check_trends
            reply = check_trends()
            send_reply(chat_id, reply)

        elif "/status" in cmd:
            print(f"[PROCESS] /status for {chat_id}")
            from market_status import market_overview
            reply = market_overview()
            send_reply(chat_id, reply)

    except Exception as e:
        print(f"[ERROR] handle_command: {e}")
        send_reply(chat_id, f"❌ Error: {str(e)[:100]}")


def run_bot():
    """Main bot loop."""
    global last_update_id
    print(f"[START] Trading Bot — {datetime.now().strftime('%H:%M UTC')}")
    print("Commands: /price, /trend, /status\n")

    while True:
        try:
            updates = get_updates()

            for update in updates:
                last_update_id = max(last_update_id, update.get("update_id", 0))

                # Handle direct messages
                if "message" in update:
                    msg = update["message"]
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    if text and text.startswith("/"):
                        print(f"[MSG] {text} from {chat_id}")
                        handle_command(chat_id, text)

                # Handle channel posts
                elif "channel_post" in update:
                    msg = update["channel_post"]
                    text = msg.get("text", "")
                    chat_id = msg.get("chat", {}).get("id")

                    if text and text.startswith("/"):
                        print(f"[CH] {text} from {chat_id}")
                        handle_command(chat_id, text)

            if not updates:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[STOP] Bot stopped.")
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
