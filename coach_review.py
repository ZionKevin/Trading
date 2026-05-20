# -*- coding: utf-8 -*-
"""Trading Coach Review — interactive trade journal + Telegram review."""
import requests
import json
from datetime import datetime
from pathlib import Path

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHAT_ID = "1085188912"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

TRADE_LOG = "C:\\Projects\\Trading\\trade_log.json"


def send_review(review_text):
    """Gửi review qua Telegram."""
    payload = {
        "chat_id": CHAT_ID,
        "text": review_text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(TELEGRAM_API, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def log_trade(symbol, entry, sl, tp, exit_price, pnl, reason=""):
    """Log trade vào file JSON."""
    trade = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "exit": exit_price,
        "pnl": pnl,
        "reason": reason
    }

    # Load existing trades
    trades = []
    if Path(TRADE_LOG).exists():
        try:
            with open(TRADE_LOG, "r", encoding="utf-8") as f:
                trades = json.load(f)
        except:
            trades = []

    trades.append(trade)

    # Save
    with open(TRADE_LOG, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

    return trade


def analyze_trade(entry, sl, tp, exit_price, pnl):
    """Phân tích trade."""
    analysis = {
        "entry_ok": True,  # tạm thời, user confirm
        "exit_ok": False,
        "pnl": pnl,
        "feedback": []
    }

    # Check exit
    if pnl > 0:
        analysis["exit_ok"] = True
        analysis["feedback"].append("✅ Lệnh thắng, exit đúng")
    else:
        analysis["feedback"].append(f"❌ Lệnh thua: ${abs(pnl):.0f}")

    # Check entry vs SL distance
    risk = abs(entry - sl)
    if pnl > 0:
        rr = pnl / risk if risk > 0 else 0
        analysis["feedback"].append(f"R:R = {rr:.2f}x")

    return analysis


def interactive_review():
    """Interactive coaching session."""
    print("\n" + "="*60)
    print("TRADING COACH - Trade Review")
    print("="*60)

    symbol = input("\n📍 Symbol (XAU/BTC): ").strip().upper()
    entry = float(input("📊 Entry Price: $"))
    sl = float(input("🛑 Stop Loss: $"))
    tp = input("🎁 TP Target (e.g., 4540-4530): ").strip()
    exit_price = float(input("❌ Exit Price (actual): $"))
    lot = float(input("📦 Lot Size: "))

    # Calculate PnL
    if symbol in ["XAU", "XAG"]:
        # For commodities, per oz
        pnl = (exit_price - entry) * lot * 100  # Rough estimate
    else:
        pnl = (exit_price - entry) * lot * 1000  # Crypto rough

    # Confirm
    print(f"\n--- SUMMARY ---")
    print(f"Entry: ${entry:,.2f} | Exit: ${exit_price:,.2f}")
    print(f"PnL: ${pnl:,.0f}")
    confirm = input("Confirm? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    # Log trade
    log_trade(symbol, entry, sl, tp, exit_price, pnl)

    # Analysis
    analysis = analyze_trade(entry, sl, tp, exit_price, pnl)

    # Generate review
    review = f"""
📋 **TRADE REVIEW** - {symbol}

**Setup:**
Entry: ${entry:,.2f}
SL: ${sl:,.2f}
TP: {tp}

**Result:**
Exit: ${exit_price:,.2f}
PnL: ${pnl:,.0f}

**Feedback:**
{chr(10).join(analysis['feedback'])}

⏰ Time: {datetime.now().strftime('%H:%M %d/%m/%Y')}
"""

    print("\n" + review)

    # Send to Telegram
    if send_review(review):
        print("✅ Review sent to Telegram")
    else:
        print("❌ Failed to send review")


def stats():
    """Show trade statistics."""
    if not Path(TRADE_LOG).exists():
        print("No trade log found.")
        return

    with open(TRADE_LOG, "r", encoding="utf-8") as f:
        trades = json.load(f)

    total_pnl = sum(t["pnl"] for t in trades)
    win_count = sum(1 for t in trades if t["pnl"] > 0)
    loss_count = sum(1 for t in trades if t["pnl"] < 0)
    win_rate = win_count / len(trades) * 100 if trades else 0

    stats_text = f"""
📊 **TRADING STATS**

Total Trades: {len(trades)}
Wins: {win_count} | Losses: {loss_count}
Win Rate: {win_rate:.1f}%

**Total PnL: ${total_pnl:,.0f}**

---
Recent 5 trades:
"""
    for t in trades[-5:]:
        pnl_emoji = "✅" if t["pnl"] > 0 else "❌"
        stats_text += f"\n{pnl_emoji} {t['symbol']}: ${t['pnl']:,.0f}"

    print(stats_text)

    # Send to Telegram
    send_review(stats_text)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats()
    else:
        interactive_review()
