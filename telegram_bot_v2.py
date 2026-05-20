# -*- coding: utf-8 -*-
"""Telegram bot with DM + channel support."""
import logging
import re
import asyncio
from telegram import Bot, Update
from telegram.error import TelegramError
from price_check import check_prices
from trend_check import check_trends
from market_status import market_overview
from scalp_check import check_h1_trend, check_m5_scalp, check_m15_scalp, find_scalp_entry
from fetch import fetch_symbol
from indicators import IndicatorSet
from trade_log import log_entry, close_trade, format_stats, list_trades, load_trades
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
CHANNEL_ID = "@Zion_XAU_Signals"
bot = Bot(token=BOT_TOKEN)

last_update_id = 0
last_alert_time = {}  # Track last alert per timeframe to avoid spam


async def get_updates():
    """Poll for new messages."""
    global last_update_id
    try:
        updates = await bot.get_updates(offset=last_update_id + 1, timeout=30)
        if updates:
            last_update_id = max(u.update_id for u in updates)
        return updates
    except Exception as e:
        logger.error(f"getUpdates error: {e}")
        return []


async def send_reply(chat_id, text):
    """Send message to chat."""
    try:
        # Send without markdown to avoid parse errors
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"[SENT] {len(text)} chars to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"send_reply error: {e}")
        return False


async def check_scalp_setup(timeframe):
    """Check if M5/M15 has setup. Return setup dict or None."""
    try:
        if timeframe == "5m":
            df = fetch_symbol("XAU", "5m", 7)
        elif timeframe == "15m":
            df = fetch_symbol("XAU", "15m", 7)
        else:
            return None

        df_h1 = fetch_symbol("XAU", "1h", 5)
        setup = find_scalp_entry(df, "XAU", df_h1)
        return setup
    except Exception as e:
        logger.error(f"check_scalp_setup {timeframe} error: {e}")
        return None


async def smart_alert_loop():
    """Background task: check M5/M15 every 5 min, alert only if setup found."""
    logger.info("[ALERT] Smart scalp alert loop started")
    alert_cooldown = 300  # 5 minutes between alerts for same timeframe

    while True:
        try:
            now = datetime.now()

            # Check M5
            setup_m5 = await check_scalp_setup("5m")
            if setup_m5:
                last_m5 = last_alert_time.get("m5", datetime.min)
                if (now - last_m5).total_seconds() > alert_cooldown:
                    dir_text = "BUY" if "BUY" in setup_m5['signal'] else "SELL"

                    # Determine action text
                    if "BOUNCE" in setup_m5['signal']:
                        action = f"Wait for bounce to {setup_m5['entry']:.2f}"
                    elif "BREAK" in setup_m5['signal']:
                        action = f"Enter on break to {setup_m5['entry']:.2f}"
                    else:
                        action = f"Enter at {setup_m5['entry']:.2f}"

                    msg = f"M5 ALERT - {dir_text}\n"
                    msg += f"Action: {action}\n"
                    msg += f"SL {setup_m5['sl']:.2f} TP {setup_m5['tp']:.2f}\n"
                    msg += f"Signal: {setup_m5['signal']}"
                    await send_reply(CHANNEL_ID, msg)
                    last_alert_time["m5"] = now
                    logger.info(f"[ALERT] M5 setup sent: {setup_m5['signal']}")

            # Check M15
            setup_m15 = await check_scalp_setup("15m")
            if setup_m15:
                last_m15 = last_alert_time.get("m15", datetime.min)
                if (now - last_m15).total_seconds() > alert_cooldown:
                    dir_text = "BUY" if "BUY" in setup_m15['signal'] else "SELL"

                    # Determine action text
                    if "BOUNCE" in setup_m15['signal']:
                        action = f"Wait for bounce to {setup_m15['entry']:.2f}"
                    elif "BREAK" in setup_m15['signal']:
                        action = f"Enter on break to {setup_m15['entry']:.2f}"
                    else:
                        action = f"Enter at {setup_m15['entry']:.2f}"

                    msg = f"M15 ALERT - {dir_text}\n"
                    msg += f"Action: {action}\n"
                    msg += f"SL {setup_m15['sl']:.2f} TP {setup_m15['tp']:.2f}\n"
                    msg += f"Signal: {setup_m15['signal']}"
                    await send_reply(CHANNEL_ID, msg)
                    last_alert_time["m15"] = now
                    logger.info(f"[ALERT] M15 setup sent: {setup_m15['signal']}")

            # Check every 5 minutes
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"smart_alert_loop error: {e}")
            await asyncio.sleep(60)


async def handle_command(chat_id, text):
    """Route command to handler."""
    cmd = text.lower().strip()

    try:
        if "/price" in cmd:
            logger.info(f"/price from {chat_id}")
            reply = check_prices()
            await send_reply(chat_id, reply)
        elif "/trend" in cmd:
            logger.info(f"/trend from {chat_id}")
            reply = check_trends()
            await send_reply(chat_id, reply)
        elif "/status" in cmd:
            logger.info(f"/status from {chat_id}")
            reply = market_overview()
            await send_reply(chat_id, reply)
        elif "/h1" in cmd:
            logger.info(f"/h1 from {chat_id}")
            reply = check_h1_trend()
            await send_reply(chat_id, reply)
        elif "/m5" in cmd:
            logger.info(f"/m5 from {chat_id}")
            reply = check_m5_scalp()
            await send_reply(chat_id, reply)
        elif "/m15" in cmd:
            logger.info(f"/m15 from {chat_id}")
            reply = check_m15_scalp()
            await send_reply(chat_id, reply)
        elif "/enter" in cmd:
            logger.info(f"/enter from {chat_id}")
            # Format: /enter SIGNAL_NAME ENTRY_PRICE
            parts = text.split()
            if len(parts) >= 3:
                signal = parts[1]
                try:
                    entry_price = float(parts[2])
                    trade = log_entry(signal, entry_price)
                    reply = f"TRADE OPENED\nID: {trade['id']}\nSignal: {signal}\nEntry: {entry_price:.2f}"
                    await send_reply(chat_id, reply)
                except ValueError:
                    await send_reply(chat_id, "Invalid price. Format: /enter SIGNAL_NAME PRICE")
            else:
                await send_reply(chat_id, "Format: /enter BUY_PIVOT_S1_BOUNCE 4550.00")
        elif "/close" in cmd:
            logger.info(f"/close from {chat_id}")
            # Format: /close EXIT_PRICE (auto-close last open trade)
            parts = text.split()
            if len(parts) >= 2:
                try:
                    exit_price = float(parts[1])

                    # Find last open trade
                    trades = load_trades()
                    open_trades = [t for t in trades if t['status'] == 'OPEN']

                    if open_trades:
                        trade_id = open_trades[-1]['id']  # Last open trade
                        trade = close_trade(trade_id, exit_price)
                        if trade:
                            reply = f"TRADE CLOSED\nID: {trade['id']}\nEntry: {trade['entry_price']:.2f}\nExit: {exit_price:.2f}\nP&L: ${trade['pnl']:.2f}"
                            await send_reply(chat_id, reply)
                        else:
                            await send_reply(chat_id, "Error closing trade")
                    else:
                        await send_reply(chat_id, "No open trades")
                except ValueError:
                    await send_reply(chat_id, "Invalid price. Use: /close 4660.00")
            else:
                await send_reply(chat_id, "Format: /close 4660.00")
        elif "/stats" in cmd:
            logger.info(f"/stats from {chat_id}")
            reply = format_stats()
            await send_reply(chat_id, reply)
        elif "/trades" in cmd:
            logger.info(f"/trades from {chat_id}")
            reply = list_trades(10)
            await send_reply(chat_id, reply)
    except Exception as e:
        logger.error(f"handle_command error: {e}")
        await send_reply(chat_id, f"ERROR: {str(e)[:100]}")


async def run_bot():
    """Main bot loop."""
    logger.info("Bot started. Listening for commands...")

    while True:
        try:
            updates = await get_updates()

            for update in updates:
                # Handle direct messages
                if update.message and update.message.text:
                    text = update.message.text
                    chat_id = update.message.chat.id
                    if text.startswith("/"):
                        logger.info(f"[MSG] {text} from {chat_id}")
                        await handle_command(chat_id, text)

                # Handle channel posts
                elif update.channel_post and update.channel_post.text:
                    text = update.channel_post.text
                    chat_id = update.channel_post.chat.id
                    if text.startswith("/"):
                        logger.info(f"[CH] {text} from {chat_id}")
                        await handle_command(chat_id, text)

            if not updates:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Bot stopped.")
            break
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            await asyncio.sleep(5)


async def main():
    """Run bot + smart alert loop concurrently."""
    await asyncio.gather(
        run_bot(),
        smart_alert_loop()
    )


if __name__ == "__main__":
    asyncio.run(main())
