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
    """Phase 6: ONE ALERT PER SESSION max (strict one-at-a-time)."""
    global alert_count_today
    logger.info("[ALERT] Phase 6: One alert per session + best signal only (NO SPAM)")
    symbols = ["XAU", "BTC", "ETH", "XAG", "USOIL", "DXY"]
    symbol_emojis = {"XAU": "🥇", "BTC": "🔵", "ETH": "⬜", "XAG": "🪙", "USOIL": "🛢️", "DXY": "💹"}

    while True:
        try:
            now = datetime.now()
            current_hour_utc = now.hour

            # Check if there's already a pending alert in current session
            pending = get_pending_alerts()
            if pending:
                logger.info(f"[INFO] {len(pending)} alert(s) pending, skip posting (one-at-a-time)")
                await asyncio.sleep(300)
                continue

            session_info = get_current_session(current_hour_utc)
            session_name = session_info['session']

            # Get BEST signal (highest win rate from top 3)
            top_signals = get_top_signals(limit=3)
            if not top_signals:
                logger.info("[SKIP] No qualified signals (need >=50% WR and >=5 trades)")
                await asyncio.sleep(300)
                continue

            best_signal = top_signals[0]  # Top signal by win rate
            signal_confidence = get_signal_confidence(best_signal)
            logger.info(f"[SCAN] Best signal: {best_signal} (conf {signal_confidence:.0f}%)")

            # Scan all symbols for this signal
            best_setup = None
            best_sym = None
            best_tf = None

            for sym in symbols:
                h1_trend = await get_h1_trend(sym)
                is_buy = "BUY" in best_signal
                trend_aligned = (is_buy and h1_trend == "UP") or (not is_buy and h1_trend == "DOWN")

                if not trend_aligned:
                    continue

                # Check session skip rule (C+D)
                skip_session, _ = should_skip_session(current_hour_utc, signal_confidence)
                if skip_session:
                    continue

                # Check M5
                setup_m5 = check_symbol_setup(sym, "5m")
                if setup_m5 and setup_m5['signal'] == best_signal and setup_m5['volume_is_strong']:
                    best_setup = setup_m5
                    best_sym = sym
                    best_tf = "5m"
                    break  # Found best_signal on M5, use it

                # Check M15 if no M5 match
                setup_m15 = check_symbol_setup(sym, "15m")
                if setup_m15 and setup_m15['signal'] == best_signal and setup_m15['volume_is_strong']:
                    best_setup = setup_m15
                    best_sym = sym
                    best_tf = "15m"
                    # Don't break; keep searching M5 across other symbols

            if not best_setup:
                logger.info(f"[SKIP] {best_signal} not found with good setup this cycle")
                await asyncio.sleep(300)
                continue

            # Found best_setup, post it
            h1_trend = await get_h1_trend(best_sym)
            is_buy = "BUY" in best_setup['signal']
            dir_text = "BUY" if is_buy else "SELL"
            emoji = symbol_emojis.get(best_sym, "📍")

            # Generate action text based on signal type
            signal = best_setup['signal']
            entry = best_setup['entry']

            if "FIBO" in signal:
                # Fibonacci: show trend + which level to test
                # Uptrend (BUY): test Fibo on the way up
                # Downtrend (SELL): test Fibo on the way down
                trend_text = "nhịp tăng" if is_buy else "nhịp giảm"
                level_text = "38.2%" if "38" in signal else "61.8%"
                action = f"Chờ giá test Fibo {level_text} của {trend_text} và {dir_text}"
            elif "SUPPORT" in signal and "BREAK" in signal:
                # Support BREAK: break below support, then buy (counter-trend risky)
                action = f"Chờ giá break hỗ trợ {entry:.0f}, sau đó {dir_text}"
            elif "SUPPORT" in signal or "S1" in signal:
                # Support bounce: buy at support
                action = f"Chờ {dir_text} ở hỗ trợ {entry:.0f}"
            elif "RESISTANCE" in signal and "BREAK" in signal:
                # Resistance BREAK: break above resistance, then sell (counter-trend risky)
                action = f"Chờ giá break cản {entry:.0f}, sau đó {dir_text}"
            elif "RESISTANCE" in signal or "R1" in signal:
                # Resistance bounce: sell at resistance
                action = f"Chờ {dir_text} ở cản {entry:.0f}"
            elif "MA89" in signal:
                # MA89 bounce
                action = f"Chờ {dir_text} ở MA89 ({entry:.0f})"
            elif "TRENDLINE" in signal:
                # Trendline break
                action = f"Chờ giá phá trendline {entry:.0f}, sau đó {dir_text}"
            else:
                action = f"Vào lệnh ở {entry:.0f}"

            # Boost confidence for Fibo+rejection confluence (high quality setup)
            final_confidence = signal_confidence
            confluence_label = ""
            if best_setup.get('fibo_info') and best_setup['fibo_info'].get('confluence'):
                if best_setup['fibo_info']['confluence'].get('has_confluence'):
                    final_confidence = min(100, signal_confidence + 15)  # +15 confidence boost
                    confluence_label = " 🎯 Confluence"

            # Track alert FIRST to get ID (with TP levels if Fibo)
            alert_id = post_alert(best_sym, best_tf, best_setup['signal'], best_setup['entry'],
                                 best_setup['sl'], best_setup['tp'], h1_trend, final_confidence, session_name,
                                 tp1=best_setup.get('tp1'), tp3=best_setup.get('tp3'))

            msg = f"🔔 Alert #{alert_id}\n"
            msg += f"{emoji} {best_tf.upper()} {best_sym} — {dir_text}\n"
            msg += f"Action: {action}\n"
            msg += f"SL {best_setup['sl']:.0f}\n"

            # Show TP levels (3 for Fibo, 1 for ATR-based)
            if best_setup.get('tp1') and best_setup.get('tp3'):
                msg += f"TP1 {best_setup['tp1']:.0f} | TP2 {best_setup['tp']:.0f} | TP3 {best_setup['tp3']:.0f}\n"
            else:
                msg += f"TP {best_setup['tp']:.0f}\n"

            msg += f"Signal: {best_setup['signal']}{confluence_label}\n"
            msg += f"Conf: {final_confidence:.0f}% | H1: {h1_trend} | Session: {session_name}\n"
            msg += f"Report: /tp {alert_id} or /sl {alert_id} or /exit {alert_id} <price>"

            await send_reply(CHANNEL_ID, msg)
            alert_count_today += 1
            logger.info(f"[ALERT] #{alert_id} {best_sym} {best_tf} {best_setup['signal']} posted (conf {signal_confidence:.0f})")

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
            reply = "Bot auto-scans every 5 min (Phase 6 one-at-a-time). No manual /enter needed.\nJust wait for 🔔 Alert or use /open to see pending."
            await send_reply(chat_id, reply)
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
            # Format: /tp <alert_id> [tp_level] (mark as TP hit)
            # tp_level: 1 (127.2%), 2 (161.8%), 3 (200%), or omit for primary
            parts = text.split()
            if len(parts) >= 2:
                try:
                    alert_id = int(parts[1])
                    tp_level = None
                    if len(parts) >= 3:
                        tp_level = int(parts[2])  # Which TP hit: 1, 2, or 3

                    closed = close_alert(alert_id, "TP", tp_level=tp_level)
                    if closed:
                        tp_label = f" TP{tp_level}" if tp_level else ""
                        reply = f"Alert #{alert_id} closed:{tp_label} TP hit! +${abs(closed['pnl']):.0f} profit"
                    else:
                        reply = f"Alert #{alert_id} not found"
                except ValueError:
                    reply = "Format: /tp <alert_id> [1|2|3]"
            else:
                reply = "Format: /tp <alert_id> [1|2|3]"
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
