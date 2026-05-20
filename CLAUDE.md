# XAU Scalp Trading Bot — Project Context

## 1. Tổng Quan
- **Loại:** Telegram bot for XAU (Gold) scalp trading signals
- **Mục tiêu:** Real-time M5/M15 scalp alerts + trade logging + backtesting
- **Tech stack:** Python 3.12 · python-telegram-bot · yfinance · pandas · numpy
- **Status:** Phase 3 (Multi-symbol + Daily Reports) ✅ · Backtesting (Phase 4) 🔄

---

## 2. Architecture

### Files
```
Trading/
├── telegram_bot_v2.py      ← Main bot (polling, commands, alerts)
├── scalp_check.py          ← Scalp signal detection (M5/M15)
├── indicators.py           ← Technical indicators (RSI, ATR, MA, etc)
├── fetch.py                ← yfinance data loader (6 symbols)
├── price_check.py          ← /price command formatter
├── trend_check.py          ← /trend command formatter
├── market_status.py        ← /status command formatter
├── trade_log.py            ← Trade journal + P&L + daily stats
├── backtest.py             ← 30-day backtest validator (NEW)
├── trades.json             ← Trade history (auto-generated)
├── requirements.txt        ← Dependencies
└── CLAUDE.md               ← This file
```

### Symbols (6)
- XAU (Gold) · BTC · ETH · XAG (Silver) · USOIL (Oil) · DXY (Dollar Index)
- Each mapped to yfinance tickers: XAU→GC=F, BTC→BTC-USD, ETH→ETH-USD, etc.

---

## 3. Features Completed

### Phase 1 — Core Bot + XAU Scalp
✅ Daily technical analysis (RSI, MA, pivot, Dow Theory, SuperTrend)
✅ M5/M15 scalp signal detection (bounce + breakout)
✅ Telegram polling bot with /commands
✅ Trade logging (/enter, /close, /stats, /trades)
✅ P&L calculation per trade + per signal

### Phase 2 — Smart Alerts (Volume + Consolidation)
✅ Volume confirmation (breakout volume > 120% of 20-day avg)
✅ Consolidation detection (ATR < 70% of average)
✅ Auto-post alerts only when **both** conditions met (no spam)
✅ 5-min cooldown per symbol+timeframe (prevents duplicate alerts)

### Phase 3 — Multi-Symbol + Daily Reports
✅ Extended bot to monitor all 6 symbols (XAU, BTC, ETH, XAG, USOIL, DXY)
✅ Separate emoji prefix per symbol (🥇 XAU, 🔵 BTC, ⬜ ETH, 🪙 XAG, 🛢️ USOIL, 💹 DXY)
✅ Daily stats report (7 PM auto-post): wins, losses, P&L, signal breakdown
✅ Independent alert tracking per symbol+timeframe

### Phase 4 — Backtesting (IN PROGRESS)
🔄 30-day historical backtest for all 6 symbols
🔄 Win rate validation per signal type
🔄 Max drawdown, Sharpe ratio, RRR metrics
🔄 Trade-by-trade simulation with SL/TP exits

---

## 4. Quy Ước & Tính Năng

### Scalp Signal Logic
**Bounce Signals:**
- BUY_MA89_BOUNCE: Price touches EMA89 (Close) ±2 pips
- BUY_SUPPORT_BOUNCE: Price touches recent support level
- BUY_PIVOT_S1_BOUNCE: Price touches pivot S1 level
- SELL_RESISTANCE_BOUNCE: Price touches recent resistance
- SELL_PIVOT_R1_BOUNCE: Price touches pivot R1 level

**Breakout Signals:**
- BUY_TRENDLINE_BREAKUP: Break above trendline (higher lows detected)
- BUY_SUPPORT_BREAK: Strong break below support (−3 pips)
- SELL_TRENDLINE_BREAKDN: Break below trendline (lower highs detected)
- SELL_RESISTANCE_BREAK: Strong break above resistance (+3 pips)

**Phase 2 Filters:**
- volume_is_strong = current_volume > 120% of 20-day avg
- is_consolidating = current_ATR < 70% of 20-day avg
- Alert posts ONLY if both = true (confidence boost)

### Risk/Reward
- SL: 6 pips (fixed for now, can tune per symbol)
- TP: 10 pips (fixed for now, can tune per symbol)
- Lot: 0.2 (default, /enter accepts custom)
- P&L formula: (exit_price − entry_price) × $10/pip × lot_size

### Daily Report (7 PM VN time)
- Today's closed trades + open trades
- Win rate % + Wins/Losses count
- Total P&L + Average win/loss
- Per-signal breakdown (win%, P&L)
- Alert count for the day

---

## 5. Commands (Telegram)

### Market Analysis
- `/price` → Current prices (6 symbols) + RSI + trend
- `/trend` → H1 trend direction per symbol (RSI-based)
- `/status` → Market overview (volatility, key levels, pivot points)
- `/h1` → H1 macro trend (macro direction check)

### Scalp Checks
- `/m5` → M5 setup analysis (all 6 symbols, action text, volume, consolidation)
- `/m15` → M15 setup analysis (same as M5)

### Trade Management
- `/enter SIGNAL_NAME PRICE` → Log trade entry (auto-generates ID)
- `/close PRICE` → Close last open trade + log P&L
- `/stats` → Total stats (win rate, RRR, P&L all-time, per-signal breakdown)
- `/trades` → List recent 10 trades (ID, signal, entry→exit, P&L status)

---

## 6. Bot Flow

### Startup
```
asyncio.gather(
  run_bot()              ← Polling for /commands, reply to chat
  smart_alert_loop()     ← Check all 6 symbols M5/M15 every 5 min
  daily_report_task()    ← Post daily summary at 7 PM
)
```

### Alert Loop (every 5 min)
```
For each symbol (XAU, BTC, ETH, XAG, USOIL, DXY):
  For each timeframe (M5, M15):
    Check setup = find_scalp_entry()
    IF setup AND volume_strong AND consolidating:
      IF (now − last_alert[symbol_tf]) > 300 sec:
        Post alert to channel
        Increment alert_count_today
        Set last_alert[symbol_tf] = now
```

### Daily Report (7 PM)
```
Call format_daily_stats() → today's closed trades
Add alert_count_today
Post to channel
Reset alert_count_today = 0
```

---

## 7. Dev Instructions

### Test Locally
```bash
python telegram_bot_v2.py          # Start bot
# Mở Telegram → post /price hoặc /m5 để test
```

### Backtest
```bash
python backtest.py                 # 30-day backtest all symbols
# Output: win rate, P&L, max drawdown per symbol+signal
```

### Add New Symbol
1. Add to `symbols` list in `telegram_bot_v2.py` smart_alert_loop()
2. Add emoji in `symbol_emojis` dict
3. Ensure yfinance ticker mapping in `fetch.py`
4. Re-run backtest to validate

### Tune SL/TP
- Edit `find_scalp_entry()` in scalp_check.py
- Current: SL = entry ± 6, TP = entry ± 10
- Can make dynamic based on ATR: SL = entry ± ATR, TP = entry ± 2×ATR

---

## 8. Known Limitations & TODOs

### Limitation
- SL/TP fixed (not dynamic ATR-based yet)
- No auto-trade execution (manual /enter only)
- Backtest doesn't account for slippage/commissions
- Self-learning not implemented yet (next phase)

### TODO (Future Phases)
- [ ] Dynamic SL/TP based on ATR per symbol
- [ ] Self-learning: track which signal types have highest win rate
- [ ] Trend filtering: only alert if macro trend (H1) aligns
- [ ] Auto-trade execution (broker API integration)
- [ ] Slippage/commission modeling in backtest
- [ ] Real-time P&L dashboard

---

## 9. Reference

### Telegram
```
Bot Token:  8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY
Channel:    @Zion_XAU_Signals (public)
Personal:   ID 1085188912
```

### Data Source
yfinance (free, no API key needed)

### Trade Sizes & Risk
Default 0.2 lot, SL $60 (6 pips × $10 × 0.2), TP $200 (10 pips × $10 × 0.2)

---

## 10. Best Practices

- **Alert filtering:** NEVER post alert without volume + consolidation check (avoid false signals)
- **Trade logging:** ALWAYS log entry with /enter to track P&L
- **Backtest before deploy:** Run backtest on new signals before going live
- **Signal tuning:** Monitor win rate per signal type, disable low-confidence signals
- **Risk management:** NEVER exceed 0.5 lot on scalp trades

---

## Edit History
- **2026-05-20 Phase 1-3:** Core bot, XAU signals, multi-symbol, daily reports
- **2026-05-20 Phase 4:** Backtesting framework
