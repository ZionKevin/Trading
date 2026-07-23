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
from smc_check import analyze_symbol_smc, format_smc_analysis, format_smc_htf, SMC_SIGNALS
from session_manager import get_current_session, should_skip_session, format_session_recommendations, update_hourly_stats
from trade_tracker import post_alert, close_alert, expire_alert, get_session_alert_count, get_pending_alerts, has_open_trade, format_live_performance
from learning import get_top_signals
from fetch import fetch_symbol, pop_fallback_warning
from indicators import IndicatorSet
from trade_log import log_entry, close_trade, format_stats, list_trades, load_trades, format_daily_stats
from learning import learn_from_trades, format_learning_report, get_signal_confidence, get_enabled_signals, generate_recommendations
from trading_profile import add_taught_trade, format_profile, list_taught_trades, parse_teach_text, forget_taught_trade
from macro_analysis import generate_daily_report, generate_pre_event_alert, format_macro_summary
from news_filter import check_news_blackout, format_upcoming_news
from datetime import datetime, timedelta
import pytz

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
_news_notified = set()  # tin đã báo "tạm dừng" — tránh spam mỗi cycle 5'
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


async def daily_macro_report():
    """Send daily macro report at 1 AM US time (6 PM UTC)."""
    while True:
        try:
            now = datetime.now(pytz.UTC)
            # 1 AM EST = 6 PM UTC, 1 AM EDT = 5 PM UTC (let's use 6 PM UTC for consistency)
            if now.hour == 18 and now.minute == 0:  # 6 PM UTC = 1 AM EST
                report = generate_daily_report(0)
                await send_reply(CHANNEL_ID, report)
                logger.info("[MACRO] Daily report sent")
                await asyncio.sleep(60)  # Avoid duplicate in same minute
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"daily_macro_report error: {e}")
            await asyncio.sleep(60)


async def pre_event_alerts():
    """Send pre-event alerts 30 min before major events (5:30 AM US = 10:30 UTC)."""
    while True:
        try:
            now = datetime.now(pytz.UTC)
            # 5:30 AM EST = 10:30 UTC, 5:30 AM EDT = 9:30 UTC (check 10:30 UTC)
            if now.hour == 10 and now.minute == 30:
                alert = generate_pre_event_alert("Major Economic Event", "TBD", "TBD", 30)
                await send_reply(CHANNEL_ID, alert)
                logger.info("[MACRO] Pre-event alert sent")
                await asyncio.sleep(60)
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"pre_event_alerts error: {e}")
            await asyncio.sleep(60)


async def alert_watchdog():
    """Tự xử lý alert treo (fix bệnh 'quên /tp /sl → bot câm vĩnh viễn').

    Mỗi 10 phút, với từng alert PENDING:
    - Soi nến 5m TỪ LÚC POST: giá chạm SL trước → tự đóng SL; chạm TP → tự đóng
      đúng level cao nhất đã chạm (nến nào chạm cả 2 thì tính SL — conservative).
    - Không chạm gì suốt 4 tiếng → expire (pnl 0, không tính win/loss).
    Kết quả tự đóng vẫn được learning ghi nhận như /tp /sl tay.
    """
    WATCH_INTERVAL = 600     # 10 phút
    MAX_AGE_HOURS = 4        # alert scalp M5/M15 quá 4h không chạm gì = hết giá trị
    logger.info(f"[WATCHDOG] Started — auto TP/SL theo nến, expire sau {MAX_AGE_HOURS}h")

    while True:
        try:
            await asyncio.sleep(WATCH_INTERVAL)
            pending = get_pending_alerts()
            if not pending:
                continue

            for alert in list(pending):
                try:
                    posted = datetime.fromisoformat(alert['posted_at'])
                    age_h = (datetime.now() - posted).total_seconds() / 3600
                    is_buy = 'BUY' in alert['signal']
                    days = max(1, min(7, int(age_h / 24) + 1))

                    df = await asyncio.to_thread(fetch_symbol, alert['symbol'], '5m', days)
                    if getattr(df.index, 'tz', None) is not None:
                        df = df.copy()
                        df.index = df.index.tz_localize(None)
                    candles = df[df.index > posted]

                    sl = alert['sl']
                    tp1, tp2, tp3 = alert.get('tp1'), alert['tp'], alert.get('tp3')
                    best_tp = 0
                    outcome = None

                    for _, c in candles.iterrows():
                        hi, lo = float(c['High']), float(c['Low'])
                        sl_hit = (lo <= sl) if is_buy else (hi >= sl)
                        if sl_hit:
                            # TP đã chạm ở nến TRƯỚC đó thì tính TP, không thì SL
                            outcome = ('TP', best_tp) if best_tp > 0 else ('SL', None)
                            break
                        if is_buy:
                            if tp3 and hi >= tp3:
                                best_tp = 3
                            elif hi >= tp2:
                                best_tp = max(best_tp, 2)
                            elif tp1 and hi >= tp1:
                                best_tp = max(best_tp, 1)
                        else:
                            if tp3 and lo <= tp3:
                                best_tp = 3
                            elif lo <= tp2:
                                best_tp = max(best_tp, 2)
                            elif tp1 and lo <= tp1:
                                best_tp = max(best_tp, 1)

                    if outcome is None:
                        if best_tp > 0:
                            outcome = ('TP', best_tp)
                        elif age_h >= MAX_AGE_HOURS:
                            outcome = ('EXPIRE', None)

                    if outcome is None:
                        continue  # còn sống, chờ tiếp

                    aid = alert['id']
                    if outcome[0] == 'TP':
                        closed = close_alert(aid, 'TP', tp_level=outcome[1])
                        if closed:
                            msg = f"🤖 Auto-close Alert #{aid}: giá đã chạm TP{outcome[1]} → +${abs(closed['pnl']):.0f}"
                            await send_reply(CHANNEL_ID, msg)
                            logger.info(f"[WATCHDOG] #{aid} auto TP{outcome[1]}")
                    elif outcome[0] == 'SL':
                        closed = close_alert(aid, 'SL')
                        if closed:
                            msg = f"🤖 Auto-close Alert #{aid}: giá đã chạm SL → -${abs(closed['pnl']):.0f}"
                            await send_reply(CHANNEL_ID, msg)
                            logger.info(f"[WATCHDOG] #{aid} auto SL")
                    else:
                        expire_alert(aid)
                        msg = f"⏱️ Alert #{aid} hết hạn ({MAX_AGE_HOURS}h không chạm SL/TP) — tự đóng, không tính win/loss"
                        await send_reply(CHANNEL_ID, msg)
                        logger.info(f"[WATCHDOG] #{aid} expired")

                except Exception as e:
                    logger.error(f"alert_watchdog alert #{alert.get('id')}: {e}")

        except Exception as e:
            logger.error(f"alert_watchdog error: {e}")
            await asyncio.sleep(60)


async def smart_alert_loop():
    """Phase 10 SMC: Elliott H4 → BOS/CHoCH H1 → OB/FVG M5/M15 + nến Nhật. One-at-a-time."""
    global alert_count_today
    logger.info("[ALERT] Phase 10 SMC: XAU+BTC | Elliott bias + BOS/CHoCH + OB/FVG + candle confirm")
    symbols = ["XAU", "BTC"]
    symbol_emojis = {"XAU": "🥇", "BTC": "🔵"}

    while True:
        try:
            now = datetime.now()
            current_hour_utc = now.hour

            # Báo user nếu data vừa rớt sang yfinance (giá có thể lệch/delay)
            fallback_warn = pop_fallback_warning()
            if fallback_warn:
                await send_reply(CHANNEL_ID, fallback_warn)

            # Check if there's already a pending alert in current session
            pending = get_pending_alerts()
            if pending:
                logger.info(f"[INFO] {len(pending)} alert(s) pending, skip posting (one-at-a-time)")
                await asyncio.sleep(300)
                continue

            # News blackout: ±30' quanh tin đỏ USD (NFP/CPI/FOMC) → không bắn alert
            # (nến tin spike bay SL trong 1 giây). Fail-open: feed lỗi → chạy bình thường.
            blackout, news_ev = await asyncio.to_thread(check_news_blackout)
            if blackout:
                news_key = f"{news_ev['title']}@{news_ev['time'].isoformat()}"
                if news_key not in _news_notified:
                    _news_notified.add(news_key)
                    vn_time = news_ev['time'].astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
                    await send_reply(CHANNEL_ID,
                        f"⏸️ Tạm dừng alert: tin đỏ USD sắp ra/vừa ra\n"
                        f"📰 {news_ev['title']} — {vn_time:%H:%M} giờ VN\n"
                        f"Khoá 30' trước → 30' sau tin. Đừng vào lệnh mới lúc này, "
                        f"spike tin dễ bay SL. /news xem lịch cả tuần.")
                logger.info(f"[NEWS] Blackout: {news_ev['title']} @ {news_ev['time']}")
                await asyncio.sleep(300)
                continue

            session_info = get_current_session(current_hour_utc)
            session_name = session_info['session']

            # Default khi chưa có learning data (bootstrap) — 8 signal × 2 symbol
            # Phase 10.2: key theo CẶP "SIGNAL@SYMBOL" (học tách XAU/BTC)
            DEFAULT_SIGNALS = [f"{sig}@{sym}" for sym in symbols for sig in SMC_SIGNALS]

            # Get BEST pairs (highest win rate from top 3)
            top_signals = get_top_signals(limit=3)
            if not top_signals:
                # Bootstrap: scan tất cả default pairs khi chưa có learning data
                top_signals = DEFAULT_SIGNALS
                logger.info(f"[BOOTSTRAP] No learning data — scanning {len(DEFAULT_SIGNALS)} default signal pairs")

            # Phân tích SMC mỗi symbol/timeframe ĐÚNG 1 LẦN/cycle, offload thread
            # (mỗi lần phân tích fetch H4+H1+LTF). Trend alignment đã nằm TRONG engine
            # (H1 BOS/CHoCH + Elliott bias) — không cần filter RSI ngoài này nữa.
            setup_cache = {}
            for sym in symbols:
                setup_cache[(sym, "5m")] = await asyncio.to_thread(analyze_symbol_smc, sym, "5m")
                setup_cache[(sym, "15m")] = await asyncio.to_thread(analyze_symbol_smc, sym, "15m")

            # Loop qua từng signal trong top_signals, dừng khi tìm thấy setup
            best_setup = None
            best_sym = None
            best_tf = None
            best_signal = None
            signal_confidence = 0

            for candidate_key in top_signals:
                # Key dạng "BUY_SMC_OB@XAU"; key cũ không có "@" thì match mọi symbol
                candidate_signal, _, key_sym = candidate_key.partition('@')
                candidate_conf = get_signal_confidence(candidate_key)

                # Check session skip rule
                skip_session, _ = should_skip_session(current_hour_utc, candidate_conf)
                if skip_session:
                    continue

                for sym in symbols:
                    if key_sym and sym != key_sym:
                        continue  # pair học riêng symbol nào chỉ áp cho symbol đó
                    for tf in ("5m", "15m"):
                        setup = setup_cache[(sym, tf)]
                        if setup and setup['signal'] == candidate_signal and setup['volume_is_strong']:
                            best_setup = setup
                            best_sym = sym
                            best_tf = tf
                            best_signal = candidate_signal
                            signal_confidence = candidate_conf
                            break
                    if best_setup:
                        break

                if best_setup:
                    break  # Found a setup, stop scanning more signals

            if not best_setup:
                logger.info(f"[SKIP] No good setup found across {len(top_signals)} signals × {len(symbols)} symbols this cycle")
                await asyncio.sleep(300)
                continue

            logger.info(f"[SCAN] Found {best_signal} on {best_sym} {best_tf} (conf {signal_confidence:.0f}%)")

            # Found best_setup, post it — alert đầy đủ ngữ cảnh SMC
            ctx = best_setup['context']
            is_buy = best_setup['direction'] == 'UP'
            dir_text = "BUY" if is_buy else "SELL"
            emoji = symbol_emojis.get(best_sym, "📍")
            h1_trend = ctx['h1_trend']
            signal = best_setup['signal']
            entry = best_setup['entry']

            action = f"Chờ giá test {ctx['zone_text']} và {dir_text}"

            # Boost confidence: OB+FVG chồng / nến mạnh / quét Asian / Fibo OTE / killzone
            final_confidence = signal_confidence
            boosts = []
            if ctx['has_confluence']:
                final_confidence = min(100, final_confidence + 15)
                boosts.append("OB+FVG")
            if ctx['candle_strength'] >= 3:
                final_confidence = min(100, final_confidence + 10)
                boosts.append("nến mạnh")
            if ctx.get('asian_sweep'):
                final_confidence = min(100, final_confidence + 15)
                boosts.append("quét Asian")
            if ctx.get('in_ote'):
                final_confidence = min(100, final_confidence + 10)
                boosts.append("Fibo OTE")
            if ctx.get('killzone'):
                final_confidence = min(100, final_confidence + 5)
                boosts.append("killzone")
            boost_label = f" 🎯 {'+'.join(boosts)}" if boosts else ""

            # Track alert FIRST to get ID
            alert_id = post_alert(best_sym, best_tf, signal, entry,
                                 best_setup['sl'], best_setup['tp'], h1_trend, final_confidence, session_name,
                                 tp1=best_setup.get('tp1'), tp3=best_setup.get('tp3'))

            msg = f"🔔 Alert #{alert_id}\n"
            msg += f"{emoji} {best_tf.upper()} {best_sym} — {dir_text}\n"
            msg += f"Action: {action}\n"
            msg += f"Entry {entry:.1f} | SL {best_setup['sl']:.1f}\n"
            msg += f"TP1 {best_setup['tp1']:.1f} | TP2 {best_setup['tp']:.1f} | TP3 {best_setup['tp3']:.1f}\n"
            msg += "――――――――――\n"
            msg += f"🌊 {ctx['elliott_label']}\n"
            if ctx['elliott_warning']:
                msg += f"⚠️ {ctx['elliott_warning']}\n"
            msg += f"📐 H1: {ctx['h1_event']} — trend {h1_trend}\n"
            msg += f"📦 Zone: {ctx['zone_text']} | {ctx['pd_text']}\n"
            if ctx.get('in_ote'):
                msg += "📏 Zone nằm trong Fibo OTE (hồi 61.8–79%)\n"
            if ctx.get('asian_sweep') and ctx.get('asian_range'):
                ar = ctx['asian_range']
                if is_buy:
                    msg += f"🧹 Đã quét ĐÁY phiên Á ({ar['low']:.0f}) — liquidity grab ủng hộ BUY\n"
                else:
                    msg += f"🧹 Đã quét ĐỈNH phiên Á ({ar['high']:.0f}) — liquidity grab ủng hộ SELL\n"
            if ctx.get('killzone'):
                kz_name = 'London' if ctx['killzone'] == 'LONDON' else 'New York'
                msg += f"⏰ Đang trong {kz_name} Killzone — giờ vàng chạy mạnh\n"
            if ctx['candle']:
                msg += f"🕯️ Nến: {ctx['candle']}\n"
            if ctx['liquidity_pools']:
                pools_txt = ", ".join(f"{p:.0f}" for p in ctx['liquidity_pools'])
                msg += f"💧 Liquidity target: {pools_txt}\n"
            msg += "――――――――――\n"
            msg += f"Signal: {signal}{boost_label}\n"
            msg += f"Conf: {final_confidence:.0f}% | Session: {session_name}\n"
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
            reply = await asyncio.to_thread(check_prices)
            await send_reply(chat_id, reply)
        elif "/trend" in cmd:
            logger.info(f"/trend from {chat_id}")
            reply = await asyncio.to_thread(check_trends)
            await send_reply(chat_id, reply)
        elif "/status" in cmd:
            logger.info(f"/status from {chat_id}")
            reply = await asyncio.to_thread(market_overview)
            await send_reply(chat_id, reply)
        elif "/h1" in cmd:
            logger.info(f"/h1 from {chat_id}")
            reply = await asyncio.to_thread(format_smc_htf)
            await send_reply(chat_id, reply)
        elif "/m5" in cmd:
            logger.info(f"/m5 from {chat_id}")
            reply = await asyncio.to_thread(format_smc_analysis, "5m")
            await send_reply(chat_id, reply)
        elif "/m15" in cmd:
            logger.info(f"/m15 from {chat_id}")
            reply = await asyncio.to_thread(format_smc_analysis, "15m")
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
        elif "/trades-taught" in cmd:
            logger.info(f"/trades-taught from {chat_id}")
            reply = list_taught_trades(10)
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
        elif "/teach" in cmd or "/day" in cmd:
            logger.info(f"/teach|/day from {chat_id}")
            # Gõ tự do — parser tự hiểu: /day buy 4150 sl 4140 tp 4170 test OB
            body = re.sub(r'^/(teach|day)\S*\s*', '', text.strip(), flags=re.IGNORECASE)
            if not body:
                reply = ("Dạy tao 1 lệnh mày đã đánh — gõ thoải mái, không cần đúng thứ tự:\n"
                         "• /day buy 4150 sl 4140 tp 4170 test OB H1 + nến engulfing\n"
                         "• /day 4150 4140 4170 CHoCH xong quét liquidity\n"
                         "• /day sell btc 63500 sl 63900 tp 62800 FVG premium")
            else:
                parsed, err = parse_teach_text(body)
                if err:
                    reply = err
                else:
                    trade = add_taught_trade(parsed['entry'], parsed['sl'], parsed['tp'],
                                             parsed['reason'], symbol=parsed['symbol'],
                                             timeframe=parsed['timeframe'])
                    risk = abs(parsed['entry'] - parsed['sl'])
                    reward = abs(parsed['tp'] - parsed['entry'])
                    rrr = reward / risk if risk > 0 else 0
                    reply = f"✅ Đã học lệnh #{trade['id']} — tao hiểu thế này, sai thì /day lại:\n"
                    reply += f"{parsed['direction']} {parsed['symbol']} ({parsed['timeframe']})\n"
                    reply += f"Entry {parsed['entry']:g} | SL {parsed['sl']:g} | TP {parsed['tp']:g} (RRR 1:{rrr:.1f})\n"
                    reply += f"Lý do: {parsed['reason']}\n\n"
                    reply += "/mystyle để xem profile"
                    logger.info(f"[TEACH] #{trade['id']} {parsed['direction']} {parsed['symbol']}: {parsed['reason']}")
            await send_reply(chat_id, reply)
        elif "/forget" in cmd:
            logger.info(f"/forget from {chat_id}")
            # /forget <id> — xoá 1 lệnh đã dạy (dạy nhầm/test)
            parts = text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                removed = forget_taught_trade(int(parts[1]))
                if removed:
                    reply = f"🗑️ Đã quên lệnh #{removed['id']}: {removed['direction']} {removed['symbol']} "
                    reply += f"entry {removed['entry']:g} — \"{removed['reason'][:50]}\"\n"
                    reply += "Profile đã tính lại. /mystyle để xem."
                else:
                    reply = f"Không tìm thấy lệnh dạy #{parts[1]}. Gõ /trades-taught để xem danh sách ID."
            else:
                reply = "Format: /forget <id>\nGõ /trades-taught để xem ID các lệnh đã dạy."
            await send_reply(chat_id, reply)
        elif "/mystyle" in cmd:
            logger.info(f"/mystyle from {chat_id}")
            reply = format_profile()
            await send_reply(chat_id, reply)
        elif "/news" in cmd:
            logger.info(f"/news from {chat_id}")
            reply = await asyncio.to_thread(format_upcoming_news)
            await send_reply(chat_id, reply)
        elif "/macro" in cmd:
            logger.info(f"/macro from {chat_id}")
            reply = await asyncio.to_thread(generate_daily_report, 0)
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
    """Auto-learn every hour: analyze trades, update signal confidence.

    CHỈ post khuyến nghị khi nội dung THAY ĐỔI so với lần post trước
    (có lệnh mới đóng làm số liệu đổi) — trước đây post y hệt mỗi giờ, spam channel.
    """
    logger.info("[LEARNING] Auto-learning task started (runs hourly, post on change)")
    last_posted_recs = None

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

            # Get recommendations — chỉ post khi ĐỔI
            recs = generate_recommendations()
            if recs and recs != last_posted_recs:
                last_posted_recs = recs
                msg = "[AUTO-LEARNING UPDATE]\n" + recs
                await send_reply(CHANNEL_ID, msg)
                logger.info("[LEARNING] Posted recommendations to channel (changed)")
            elif recs:
                logger.info("[LEARNING] Recommendations unchanged — skip posting")

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
    """Run bot + smart alert loop + daily report + auto-learning + macro analysis concurrently."""
    await asyncio.gather(
        run_bot(),
        smart_alert_loop(),
        alert_watchdog(),
        auto_learning_task(),
        daily_report_task(),
        daily_macro_report(),
        pre_event_alerts()
    )


if __name__ == "__main__":
    asyncio.run(main())
