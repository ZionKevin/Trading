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
from scalp_check import check_h1_trend, check_m5_scalp, check_m15_scalp, find_scalp_entry, check_symbol_setup
from market_structure import detect_rejection_candle, detect_support_hold, get_last_n_rejections, calculate_optimal_sl_tp
from session_manager import get_current_session, should_skip_session, format_session_recommendations, update_hourly_stats
from trade_tracker import post_alert, close_alert, get_session_alert_count, get_pending_alerts, has_open_trade, format_live_performance
from learning import get_top_signals
from fetch import fetch_symbol
from indicators import IndicatorSet
from trade_log import log_entry, close_trade, format_stats, list_trades, load_trades, format_daily_stats
from learning import learn_from_trades, format_learning_report, get_signal_confidence, get_enabled_signals, generate_recommendations
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
last_alert_time = {}  # Track last alert per symbol+timeframe+signal
last_alert_entry = {}  # Track last entry price for duplicate detection
alert_count_today = 0  # Track alerts posted today
ALERT_COOLDOWN = 1800  # 30 minutes (not 5 min!) — prevent spam
PRICE_MOVE_THRESHOLD = 2  # Only alert if entry price moved >2 pips from last alert


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


async def get_h1_trend(symbol):
    """Get H1 macro trend: 'UP' if RSI<50, 'DOWN' if RSI>50, else 'NEUTRAL'."""
    try:
        df_h1 = fetch_symbol(symbol, "1h", 5)
        ind = IndicatorSet(df_h1).calculate_all()
        rsi = ind.latest('rsi')
        if rsi < 50:
            return "UP"
        elif rsi > 50:
            return "DOWN"
        else:
            return "NEUTRAL"
    except Exception as e:
        logger.error(f"get_h1_trend {symbol} error: {e}")
        return "NEUTRAL"


async def smart_alert_loop():
    """Background task: check all 6 symbols M5/M15 every 5 min with trend alignment."""
    global alert_count_today
    logger.info("[ALERT] Phase 5 scalp alert loop started (trend aligned, NO SPAM)")
    symbols = ["XAU", "BTC", "ETH", "XAG", "USOIL", "DXY"]
    symbol_emojis = {"XAU": "🥇", "BTC": "🔵", "ETH": "⬜", "XAG": "🪙", "USOIL": "🛢️", "DXY": "💹"}

    while True:
        try:
            now = datetime.now()
            current_hour_utc = now.hour  # Current UTC hour

            for sym in symbols:
                # Get H1 trend for this symbol (Phase 5: trend alignment)
                h1_trend = await get_h1_trend(sym)

                # Get M15 for market structure analysis
                try:
                    df_m15 = fetch_symbol(sym, "15m", 5)
                    rejection_m15 = detect_rejection_candle(df_m15)
                    support_m15 = detect_support_hold(df_m15)
                except Exception as e:
                    logger.error(f"Market structure analysis failed: {e}")
                    rejection_m15 = {'is_rejection': False}
                    support_m15 = {'is_holding': False}

                # Check session alert limits (C+D feature)
                session_info = get_current_session(current_hour_utc)
                session_name = session_info['session']

                # Per-session limits: Euro/American = 2-3, Asian = 4-6
                if session_name in ['EUROPEAN_AMERICAN_OVERLAP', 'AMERICAN']:
                    max_alerts_per_session = 3
                elif session_name == 'ASIAN':
                    max_alerts_per_session = 6
                else:
                    max_alerts_per_session = 2

                session_alert_count = get_session_alert_count(session_name)

                # Check M5
                setup_m5 = check_symbol_setup(sym, "5m")
                if setup_m5:
                    if setup_m5['volume_is_strong'] and setup_m5['is_consolidating']:
                        is_buy = "BUY" in setup_m5['signal']

                        # Phase 5 Step 1: Trend alignment check
                        # Only post BUY if H1 uptrending, only post SELL if H1 downtrending
                        trend_aligned = (is_buy and h1_trend == "UP") or (not is_buy and h1_trend == "DOWN")

                        if trend_aligned:
                            # Session alert limit check (max 2-3 Euro/US, 4-6 Asia)
                            if session_alert_count >= max_alerts_per_session:
                                logger.info(f"[SKIP] {sym} M5: session limit reached ({session_alert_count}/{max_alerts_per_session})")
                                continue

                            # Filter to only top win-rate signals
                            top_signals = get_top_signals(limit=3)
                            if top_signals and setup_m5['signal'] not in top_signals:
                                logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: not in top signals, post only: {top_signals}")
                                continue

                            # Phase 5 Step 4: Quality filter - check signal confidence
                            signal_confidence = get_signal_confidence(setup_m5['signal'])
                            if signal_confidence >= 50 or signal_confidence == 0:  # 0 = new signal, post it
                                alert_key = f"{sym}_m5_{setup_m5['signal']}"  # Key includes signal type
                                last_alert = last_alert_time.get(alert_key, datetime.min)
                                last_entry = last_alert_entry.get(alert_key, None)

                                # Check: cooldown expired AND entry price moved significantly
                                cooldown_ok = (now - last_alert).total_seconds() > ALERT_COOLDOWN
                                price_moved = last_entry is None or abs(setup_m5['entry'] - last_entry) > PRICE_MOVE_THRESHOLD

                                # Option C+D: Session-based filtering
                                skip_session, session_reason = should_skip_session(current_hour_utc, signal_confidence)
                                session_ok = not skip_session

                                if cooldown_ok and price_moved and session_ok:
                                    dir_text = "BUY" if is_buy else "SELL"
                                    if "BOUNCE" in setup_m5['signal']:
                                        action = f"Wait for bounce to {setup_m5['entry']:.2f}"
                                    elif "BREAK" in setup_m5['signal']:
                                        action = f"Enter on break to {setup_m5['entry']:.2f}"
                                    else:
                                        action = f"Enter at {setup_m5['entry']:.2f}"

                                    emoji = symbol_emojis.get(sym, "📍")
                                    session_info = get_current_session(current_hour_utc)
                                    msg = f"{emoji} M5 {sym} — {dir_text}\n"
                                    msg += f"Action: {action}\n"
                                    msg += f"SL {setup_m5['sl']:.0f} | TP {setup_m5['tp']:.0f}\n"
                                    msg += f"Signal: {setup_m5['signal']}\n"
                                    msg += f"Volume: {setup_m5['volume_ratio']:.2f}x | H1: {h1_trend} | Conf: {signal_confidence:.0f}\n"
                                    msg += f"Session: {session_info['session']} ({session_info['description']})\n"

                                    # Market structure context
                                    if rejection_m15['is_rejection']:
                                        msg += f"M15 Rejection: {rejection_m15['type']} ({rejection_m15['strength']}/100) ⚠️\n"
                                    if support_m15['is_holding']:
                                        msg += f"Support: Holding ({support_m15['bounces']} bounces) 📍"

                                    await send_reply(CHANNEL_ID, msg)
                                    last_alert_time[alert_key] = now
                                    last_alert_entry[alert_key] = setup_m5['entry']  # Track entry for duplicate detection

                                    # Track posted alert for TP/SL monitoring
                                    alert_id = post_alert(sym, "5m", setup_m5['signal'], setup_m5['entry'],
                                                         setup_m5['sl'], setup_m5['tp'], h1_trend, signal_confidence, session_info['session'])

                                    alert_count_today += 1
                                    logger.info(f"[ALERT] #{alert_id} {sym} M5 sent: {setup_m5['signal']} (conf {signal_confidence}, {session_info['session']})")
                                else:
                                    if not session_ok:
                                        logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: {session_reason}")
                                    elif not cooldown_ok:
                                        logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: cooldown not expired yet")
                                    elif not price_moved:
                                        logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: price barely moved ({abs(setup_m5['entry'] - last_entry):.2f} pips)")
                            else:
                                logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: confidence too low ({signal_confidence})")
                        else:
                            logger.info(f"[SKIP] {sym} M5 {setup_m5['signal']}: H1 {h1_trend} not aligned")

                # Check M15
                setup_m15 = check_symbol_setup(sym, "15m")
                if setup_m15:
                    if setup_m15['volume_is_strong'] and setup_m15['is_consolidating']:
                        is_buy = "BUY" in setup_m15['signal']

                        # Phase 5 Step 1: Trend alignment check
                        trend_aligned = (is_buy and h1_trend == "UP") or (not is_buy and h1_trend == "DOWN")

                        if trend_aligned:
                            # Phase 5 Step 4: Quality filter - check signal confidence
                            signal_confidence = get_signal_confidence(setup_m15['signal'])
                            if signal_confidence >= 50 or signal_confidence == 0:  # 0 = new signal, post it
                                alert_key = f"{sym}_m15_{setup_m15['signal']}"  # Key includes signal type
                                last_alert = last_alert_time.get(alert_key, datetime.min)
                                last_entry = last_alert_entry.get(alert_key, None)

                                # Check: cooldown expired AND entry price moved significantly
                                cooldown_ok = (now - last_alert).total_seconds() > ALERT_COOLDOWN
                                price_moved = last_entry is None or abs(setup_m15['entry'] - last_entry) > PRICE_MOVE_THRESHOLD

                                # Option C+D: Session-based filtering
                                skip_session, session_reason = should_skip_session(current_hour_utc, signal_confidence)
                                session_ok = not skip_session

                                if cooldown_ok and price_moved and session_ok:
                                    dir_text = "BUY" if is_buy else "SELL"
                                    if "BOUNCE" in setup_m15['signal']:
                                        action = f"Wait for bounce to {setup_m15['entry']:.2f}"
                                    elif "BREAK" in setup_m15['signal']:
                                        action = f"Enter on break to {setup_m15['entry']:.2f}"
                                    else:
                                        action = f"Enter at {setup_m15['entry']:.2f}"

                                    emoji = symbol_emojis.get(sym, "📍")
                                    session_info = get_current_session(current_hour_utc)
                                    msg = f"{emoji} M15 {sym} — {dir_text}\n"
                                    msg += f"Action: {action}\n"
                                    msg += f"SL {setup_m15['sl']:.0f} | TP {setup_m15['tp']:.0f}\n"
                                    msg += f"Signal: {setup_m15['signal']}\n"
                                    msg += f"Volume: {setup_m15['volume_ratio']:.2f}x | H1: {h1_trend} | Conf: {signal_confidence:.0f}\n"
                                    msg += f"Session: {session_info['session']} ({session_info['description']})\n"

                                    # Market structure context
                                    if rejection_m15['is_rejection']:
                                        msg += f"M15 Rejection: {rejection_m15['type']} ({rejection_m15['strength']}/100) ⚠️\n"
                                    if support_m15['is_holding']:
                                        msg += f"Support: Holding ({support_m15['bounces']} bounces) 📍"

                                    await send_reply(CHANNEL_ID, msg)
                                    last_alert_time[alert_key] = now
                                    last_alert_entry[alert_key] = setup_m15['entry']  # Track entry for duplicate detection
                                    alert_count_today += 1
                                    logger.info(f"[ALERT] {sym} M15 sent: {setup_m15['signal']} (conf {signal_confidence}, {session_info['session']})")
                                else:
                                    if not session_ok:
                                        logger.info(f"[SKIP] {sym} M15 {setup_m15['signal']}: {session_reason}")
                                    elif not cooldown_ok:
                                        logger.info(f"[SKIP] {sym} M15 {setup_m15['signal']}: cooldown not expired yet")
                                    elif not price_moved:
                                        logger.info(f"[SKIP] {sym} M15 {setup_m15['signal']}: price barely moved ({abs(setup_m15['entry'] - last_entry):.2f} pips)")
                            else:
                                logger.info(f"[SKIP] {sym} M15 {setup_m15['signal']}: confidence too low ({signal_confidence})")
                        else:
                            logger.info(f"[SKIP] {sym} M15 {setup_m15['signal']}: H1 {h1_trend} not aligned")

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
        elif "/learning" in cmd:
            logger.info(f"/learning from {chat_id}")
            learn_from_trades()  # Update learning data
            reply = format_learning_report()
            await send_reply(chat_id, reply)
        elif "/session" in cmd:
            logger.info(f"/session from {chat_id}")
            reply = format_session_recommendations()
            await send_reply(chat_id, reply)
        elif "/open" in cmd:
            logger.info(f"/open from {chat_id}")
            pending = get_pending_alerts()
            if pending:
                reply = "PENDING ALERTS:\n"
                for alert in pending:
                    reply += f"#{alert['id']} {alert['symbol']} {alert['signal']}: "
                    reply += f"Entry {alert['entry']:.0f}, TP {alert['tp']:.0f}, SL {alert['sl']:.0f}\n"
            else:
                reply = "No pending alerts"
            await send_reply(chat_id, reply)
        elif "/tp" in cmd:
            logger.info(f"/tp from {chat_id}")
            # Format: /tp <alert_id> (mark as TP hit)
            parts = text.split()
            if len(parts) >= 2:
                try:
                    alert_id = int(parts[1])
                    closed = close_alert(alert_id, "TP")
                    if closed:
                        reply = f"Alert #{alert_id} closed: TP hit! +${200:.0f} profit"
                    else:
                        reply = f"Alert #{alert_id} not found"
                except:
                    reply = "Format: /tp <alert_id>"
            else:
                reply = "Format: /tp <alert_id>"
            await send_reply(chat_id, reply)
        elif "/sl" in cmd:
            logger.info(f"/sl from {chat_id}")
            # Format: /sl <alert_id> (mark as SL hit)
            parts = text.split()
            if len(parts) >= 2:
                try:
                    alert_id = int(parts[1])
                    closed = close_alert(alert_id, "SL")
                    if closed:
                        reply = f"Alert #{alert_id} closed: SL hit. -${abs(closed['pnl']):.0f} loss"
                    else:
                        reply = f"Alert #{alert_id} not found"
                except:
                    reply = "Format: /sl <alert_id>"
            else:
                reply = "Format: /sl <alert_id>"
            await send_reply(chat_id, reply)
        elif "/exit" in cmd:
            logger.info(f"/exit from {chat_id}")
            # Format: /exit <alert_id> <price> (close at specific price)
            parts = text.split()
            if len(parts) >= 3:
                try:
                    alert_id = int(parts[1])
                    exit_price = float(parts[2])
                    closed = close_alert(alert_id, "EXIT", exit_price)
                    if closed:
                        pnl = closed['pnl']
                        status = "WIN" if pnl > 0 else "LOSS"
                        reply = f"Alert #{alert_id} closed: {status} at {exit_price:.0f}, P&L ${pnl:.0f}"
                    else:
                        reply = f"Alert #{alert_id} not found"
                except ValueError:
                    reply = "Format: /exit <alert_id> <price>"
            else:
                reply = "Format: /exit <alert_id> <price>"
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


async def auto_learning_task():
    """Auto-learn every hour: analyze trades, update signal confidence, post recommendations."""
    logger.info("[LEARNING] Auto-learning task started (runs hourly)")

    while True:
        try:
            now = datetime.now()
            # Schedule for top of next hour
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            sleep_seconds = (next_hour - now).total_seconds()
            await asyncio.sleep(sleep_seconds)

            # Run learning analysis
            learn_from_trades()
            logger.info("[LEARNING] Updated signal confidence scores")

            # Get recommendations
            recs = generate_recommendations()
            if recs:
                msg = "[AUTO-LEARNING UPDATE]\n" + recs
                await send_reply(CHANNEL_ID, msg)
                logger.info("[LEARNING] Posted recommendations to channel")

        except Exception as e:
            logger.error(f"auto_learning_task error: {e}")
            await asyncio.sleep(300)


async def daily_report_task():
    """Post daily report at 7 PM + reset alert count."""
    logger.info("[DAILY REPORT] Daily report task started")

    while True:
        try:
            now = datetime.now()
            # Calculate seconds until 7 PM (19:00)
            target = now.replace(hour=19, minute=0, second=0, microsecond=0)
            if now >= target:
                # If already past 7 PM, schedule for tomorrow 7 PM
                target += timedelta(days=1)

            sleep_seconds = (target - now).total_seconds()
            await asyncio.sleep(sleep_seconds)

            # Post daily report
            global alert_count_today
            report = format_daily_stats()
            report += f"\nAlerts Posted: {alert_count_today}"

            # Include learning insights in daily report
            recs = generate_recommendations()
            if recs:
                report += "\n\n" + recs

            # Include session analysis
            session_analysis = format_session_recommendations()
            if session_analysis:
                report += "\n\n" + session_analysis

            await send_reply(CHANNEL_ID, report)
            logger.info(f"[DAILY REPORT] Posted: {alert_count_today} alerts")

            # Reset counter for next day
            alert_count_today = 0

        except Exception as e:
            logger.error(f"daily_report_task error: {e}")
            await asyncio.sleep(60)


async def main():
    """Run bot + smart alert loop + daily report + auto-learning concurrently."""
    await asyncio.gather(
        run_bot(),
        smart_alert_loop(),
        auto_learning_task(),
        daily_report_task()
    )


if __name__ == "__main__":
    asyncio.run(main())
