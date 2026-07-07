# XAU Scalp Trading Bot — Project Context

## 1. Tổng Quan
- **Loại:** Telegram bot for XAU (Gold) scalp trading signals
- **Mục tiêu:** Real-time M5/M15 scalp alerts + trade logging + backtesting
- **Tech stack:** Python 3.12 · python-telegram-bot · tvDatafeed (realtime TV data, primary) + yfinance (fallback) · pandas · numpy
- **Status:** Phase 1-8 ✅ · Live trên VPS DigitalOcean (152.42.247.221)

## ⚠️ CRITICAL — Workflow code change (KHÔNG chạy bot local!)
1. Edit code trên laptop (Claude/VSCode)
2. `cd C:\Projects\Trading && git add . && git commit -m "..." && git push`
3. SSH VPS qua **Web Console** (https://cloud.digitalocean.com → Droplets → ubuntu-s-1vcpu-... → Web Console)
4. Trên VPS: `cd ~/Trading && git stash && git pull && systemctl restart trading-bot`
5. Verify: `journalctl -u trading-bot -n 20`

**TUYỆT ĐỐI KHÔNG** chạy `python telegram_bot_v2.py` trên laptop → sẽ đánh nhau với VPS bot (Telegram 409 Conflict) → cả 2 instance fail.

## VPS Info
- DigitalOcean Droplet: `ubuntu-s-1vcpu-1gb-35gb-intel-sgp1` (Singapore)
- IP: `152.42.247.221` · SSH: `root@152.42.247.221`
- Service: `systemd trading-bot` (auto-restart on crash)
- Path: `/root/Trading/`
- Python: `/usr/bin/python3` (Python 3.12)
- Repo: https://github.com/ZionKevin/Trading (master branch)
- **Web Console** (browser SSH, không cần password): DigitalOcean dashboard → droplet → button "Web Console"
- **Lệnh debug nhanh** trên VPS:
  - `systemctl status trading-bot` (Active/Failed?)
  - `journalctl -u trading-bot -n 50` (50 dòng log cuối)
  - `journalctl -u trading-bot --since "1h ago" | grep -c Conflict` (đếm 409 conflict)

---

## 2. Architecture

### Files
```
Trading/
├── telegram_bot_v2.py       ← Main bot (polling, commands, alerts, 6 tasks)
├── scalp_check.py           ← Scalp signal detection (Fibo + confluence)
├── market_structure.py      ← Fibonacci detection + rejection candles (NEW)
├── indicators.py            ← Technical indicators (RSI, ATR, MA, etc)
├── fetch.py                 ← yfinance data loader (6 symbols)
├── price_check.py           ← /price command formatter
├── trend_check.py           ← /trend command formatter
├── market_status.py         ← /status command formatter
├── trade_log.py             ← Trade journal + P&L + daily stats
├── trade_tracker.py         ← Alert tracking + P&L per TP level (NEW)
├── trading_profile.py       ← User trading style learning (NEW)
├── macro_analysis.py        ← Economic calendar + daily reports (NEW)
├── backtest.py              ← 30-day backtest validator
├── trades.json              ← Trade history (auto-generated)
├── trading_profile.json     ← User taught trades (auto-generated)
├── alert_tracker.json       ← Alert tracking + closed trades (auto-generated)
├── requirements.txt         ← Dependencies
└── CLAUDE.md                ← This file
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

### Phase 4 — Backtesting
✅ 30-day historical backtest for all 6 symbols
✅ Win rate validation per signal type
✅ Max drawdown, Sharpe ratio, RRR metrics
✅ Trade-by-trade simulation with SL/TP exits

### Phase 5 — Fibonacci Retracement + Confluence Detection
✅ Fibonacci bounce detection (38.2% + 61.8% retracement levels)
✅ Rejection candle confluence (wick_ratio > 1.5 for high-quality entries)
✅ Signal types: BUY_FIBO_38_BOUNCE, BUY_FIBO_61_BOUNCE, BUY_FIBO_38_REJECTION, etc.
✅ Confluence boost: +15% confidence when Fibo + rejection detected together
✅ Fixed bugs: H1 RSI inverted logic, symbol-blind P&L calculation, cons_info timing

### Phase 6 — Three TP Levels per Alert
✅ TP1 (127.2% extension) — Aggressive partial take
✅ TP2 (161.8% extension) — Primary golden-ratio target
✅ TP3 (200% extension) — Maximum profit asymmetric target
✅ Command: `/tp <id> [1|2|3]` for per-level exit tracking
✅ Per-level P&L calculation using correct TP price

### Phase 7 — Trading Profile Learning System
✅ Command: `/teach <entry> <sl> <tp> <reason>` — field-friendly learning via Telegram
✅ Command: `/mystyle` — shows learned trading profile with entry types + confluence factors
✅ Command: `/trades-taught` — recent taught trades with reasoning
✅ Auto-analysis: risk:reward ratio, preferred entry types, confidence assessment
✅ Persistence: trading_profile.json with user's teaching data

### Phase 8 — Macro Economic Analysis
✅ Daily macro report (1 AM US time / 6 PM UTC) with yesterday recap + today's calendar
✅ Pre-event alerts (5:30 AM US time / 10:30 UTC) for critical economic releases
✅ Event importance classification: CRITICAL (CPI, NFP, FOMC), HIGH, MEDIUM, LOW
✅ Context-aware impact analysis (CPI → USD → XAU pressure, etc.)
✅ Trading strategy recommendations (wider stops, avoid entries during release)

### Phase 9 — Production Fixes & Reliability (2026-06-09)
✅ **Bootstrap DEFAULT_SIGNALS:** smart_alert_loop fallback 16 default signals khi learning.json empty (tránh stuck `BUY_TEST conf 0%` infinite skip)
✅ **SL range per-symbol (clamp):** XAU $10-15 (100-150 pip), BTC $200-500, ETH $30-70 — không còn SL 30 pip (quá tight) hoặc 300 pip (quá rộng)
✅ **SL applies to ALL signal types:** Fibo + ATR-based (Pivot/Support/MA89/Trendline) đều dùng cùng formula clamp
✅ **Volume threshold relaxed:** 1.2x → 0.8x avg (XAU 5m thường volume yếu, 1.2 quá strict → 0 signal cả tuần)
✅ **Volume auto-pass cho Forex:** `is_strong = True if avg_vol == 0 else ratio > 0.8` (Forex OTC không có volume)
✅ **Realtime data via tvDatafeed:** Switch khỏi yfinance `GC=F` (futures delay 15-30 min) sang TradingView OANDA:XAUUSD realtime
   - Fallback graceful: nếu `import tvDatafeed` fail → tự dùng yfinance
   - VPS phải `pip install tvDatafeed`

### Phase 10 — SMC Overhaul (2026-07-07) ⭐ HỆ SIGNAL HIỆN TẠI
**Thay TOÀN BỘ hệ signal cũ (Fibo/MA89/Pivot/Trendline) bằng SMC + Elliott. Chỉ đánh XAU + BTC.**

Phân tích top-down mỗi cycle (5 phút):
```
H4  → elliott_wave.py: đếm sóng heuristic → bias khung to (sóng đẩy 1-5 / điều chỉnh ABC)
H1  → smc_structure.py: HH/HL/LH/LL + BOS/CHoCH → hướng đánh + liquidity targets
M5/M15 → Order Block + FVG chưa mitigated + nến Nhật xác nhận (candle_patterns.py)
```

**8 signal types:** `BUY/SELL_SMC_OB`, `BUY/SELL_SMC_OB_CANDLE`, `BUY/SELL_SMC_FVG`, `BUY/SELL_SMC_FVG_CANDLE`
(`_CANDLE` = có nến xác nhận: engulfing/pin bar/sao mai-hôm → chất lượng cao hơn)

**Điều kiện setup (BUY):**
1. H1 trend UP (event cuối = BOS_UP hoặc CHOCH_UP)
2. Elliott H4 bias không ngược (DOWN → bỏ)
3. KHÔNG mua vùng PREMIUM (kỷ luật discount/premium theo dealing range H1)
4. Giá đang tap OB hoặc FVG bull chưa mitigated trên M5/M15
5. Volume OK (BTC ngưỡng 0.8x, XAU auto-pass)

**SL/TP:** SL = đáy/đỉnh zone ± 0.5 ATR buffer, clamp per-symbol (XAU $10-15, BTC $200-500).
TP1/TP2/TP3 = liquidity pools H1 thật (equal highs/lows), fallback 1R/2R/3R.

**Confidence boost:** +15% nếu OB+FVG chồng nhau, +10% nếu nến xác nhận mạnh (strength 3).

**Files mới:** `smc_structure.py` · `candle_patterns.py` · `elliott_wave.py` · `smc_check.py`
**Code cũ giữ trong repo** (scalp_check.py, market_structure.py) — check_volume_strength vẫn dùng chung.
`/m5` `/m15` → SMC analysis · `/h1` → H4 Elliott + H1 structure

**Phase 10.1 (cùng ngày):**
- **`/day` (alias `/teach`) gõ tự do:** parser tự hiểu mọi thứ tự — `/day buy 4150 sl 4140 tp 4170 test OB H1`,
  `/day 4150 4140 4170 lý do`, tự nhận BUY/SELL từ vị trí SL, tự nhận BTC/XAU, tự đảo SL/TP nếu gõ nhầm chỗ.
  Keyword học style đã đổi sang SMC (OB, FVG, BOS, CHoCH, liquidity, nến, sóng...).
- **alert_watchdog (task thứ 7):** mỗi 10 phút soi nến 5m từ lúc post alert — chạm SL/TP thì TỰ ĐÓNG đúng thực tế
  (nến chạm cả 2 → tính SL, conservative), treo quá 4h → expire (pnl 0, không tính win/loss).
  → Hết bệnh "quên /tp /sl là bot câm vĩnh viễn". Learning vẫn nhận data từ auto-close.
- **backtest.py port sang SMC:** walk-forward bar-by-bar, dùng CHUNG `analyze_smc_core` với live bot,
  one-trade-at-a-time, nến chạm cả SL+TP tính SL. Chạy: `python backtest.py [days]`.
- **Fix P&L SELL bị ngược dấu** trong `close_alert` (SELL thắng TP mà pnl âm) + EXPIRED không tính vào win rate.
- **Fix `/trades-taught` bị `/trades` nuốt** (thứ tự elif).

---

## 4. Quy Ước & Tính Năng

### Scalp Signal Logic
**Primary (Phase 5) — Fibonacci Signals (checked FIRST):**
- BUY_FIBO_38_BOUNCE: Price touches Fibo 38.2% retracement level ±8 pips
- BUY_FIBO_61_BOUNCE: Price touches Fibo 61.8% retracement level ±8 pips
- BUY_FIBO_38_REJECTION: Fibo 38.2% + rejection candle (wick_ratio > 1.5) together
- BUY_FIBO_61_REJECTION: Fibo 61.8% + rejection candle confluence
- SELL equivalents (4 signal types for short direction)

**Fallback — Classic Bounce Signals:**
- BUY_MA89_BOUNCE: Price touches EMA89 (Close) ±2 pips (if no Fibo match)
- BUY_SUPPORT_BOUNCE: Price touches recent support level
- BUY_PIVOT_S1_BOUNCE: Price touches pivot S1 level
- SELL_RESISTANCE_BOUNCE: Price touches recent resistance
- SELL_PIVOT_R1_BOUNCE: Price touches pivot R1 level

**Breakout Signals:**
- BUY_TRENDLINE_BREAKUP: Break above trendline (higher lows detected)
- BUY_SUPPORT_BREAK: Strong break below support (−3 pips)
- SELL_TRENDLINE_BREAKDN: Break below trendline (lower highs detected)
- SELL_RESISTANCE_BREAK: Strong break above resistance (+3 pips)

**Filtering & Confidence (Phase 2-3):**
- volume_is_strong = current_volume > 120% of 20-day avg
- is_consolidating = current_ATR < 70% of 20-day avg
- Alert posts ONLY if both = true (confidence boost)
- **Phase 5 boost:** +15% if Fibo + rejection confluence detected (e.g., 65% → 80%)

### Risk/Reward (Phase 6 + Phase 9 SL fix)
**SL — Per-symbol clamp range** (XAU 100-150 pip preferred by user):
```python
SL_RANGE_USD = {
    'XAU':   (10, 15),     # 100-150 pip
    'BTC':   (200, 500),
    'ETH':   (30, 70),
    'XAG':   (0.2, 0.5),
    'USOIL': (0.5, 1.0),
    'DXY':   (0.3, 0.7),
}
# Fibo signals: clamp fibo_distance trong [sl_min, sl_max]
# ATR signals:  clamp 1.5×ATR  trong [sl_min, sl_max], TP = 2×SL_distance (RRR 1:2)
```

**TPs (Fibo signals only):**
- TP1: 127.2% Fibonacci extension (aggressive, quick partial)
- TP2: 161.8% Fibonacci extension (golden ratio, primary target)
- TP3: 200% Fibonacci extension (maximum profit, rare)

**Lot:** 0.2 default, /enter accepts custom

**P&L formula:** `(exit_price − entry_price) × RISK_PER_PIP[symbol] × lot_size`
- XAU: $10/pip, BTC/ETH: $0.01/pip, USOIL/DXY: $0.1/pip
- User định nghĩa 1 pip XAU = $0.10 (e.g., $10 distance = 100 pip)

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
- `/m5` → M5 setup analysis (all 6 symbols, Fibo + confluence, action text, volume)
- `/m15` → M15 setup analysis (same as M5)

### Trade Management
- `/enter SIGNAL_NAME PRICE` → Log trade entry (auto-generates ID)
- `/close PRICE` → Close last open trade + log P&L
- `/tp <id> [1|2|3]` → Close alert at specific TP level (1=127.2%, 2=161.8%, 3=200%)
- `/sl <id>` → Close alert at SL (logged as loss)
- `/stats` → Total stats (win rate, RRR, P&L all-time, per-signal breakdown)
- `/trades` → List recent 10 trades (ID, signal, entry→exit, P&L status)

### Trading Profile Learning (Phase 7)
- `/teach <entry> <sl> <tp> <reason>` → Teach bot a trade you took (field-friendly)
- `/mystyle` → Show your learned trading profile (entry types, confluence factors, RRR, confidence)
- `/trades-taught` → List recently taught trades

### Macro Economic Analysis (Phase 8)
- `/macro` → Quick summary of macro schedule + tracked events

---

## 6. Bot Flow

### Startup (6 Concurrent Tasks)
```
asyncio.gather(
  run_bot()                ← Polling for /commands (/price, /m5, /teach, /mystyle, /macro, etc.)
  smart_alert_loop()       ← Check all 6 symbols M5/M15 every 5 min (Fibo + confluence detection)
  auto_learning_task()     ← Analyze closed trades, update win rates per signal
  daily_report_task()      ← Post daily stats summary at 7 PM (wins, losses, P&L)
  daily_macro_report()     ← Post economic calendar + yesterday recap at 1 AM US (6 PM UTC)
  pre_event_alerts()       ← Post event alerts 5:30 AM US (10:30 UTC) for critical releases
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

## 8. HANDOFF — Đọc kỹ nếu mày là AI/dev mới tiếp quản project này

### Trạng thái hiện tại (2026-07-07, sau Phase 10.1)
- **Hệ signal đang chạy = SMC + Elliott (Phase 10)**, KHÔNG phải Fibo/MA89/Pivot nữa.
  Não bot nằm ở `smc_check.py` (analyze_smc_core). File cũ scalp_check.py/market_structure.py
  chỉ còn để rollback + dùng ké check_volume_strength.
- Chỉ quét **XAU + BTC** (user chọn). Learning đang gom data từ đầu (reset sạch 07/07).
- User: **trader Việt, đánh vàng dạo, không rành code** — nói tiếng Việt, giải thích đơn giản,
  ĐỪNG bắt user gõ lệnh phức tạp. User thích SL 100-150 pip XAU, RRR bất đối xứng, KHÔNG auto-trade.
- Hướng dẫn sử dụng cho user: `HUONG_DAN.md` (tiếng Việt) — sửa tính năng thì NHỚ cập nhật file này.
- Lịch sử debug đầy đủ: xem Edit History cuối file + memory của Claude Code
  (`~/.claude/projects/C--Projects-Trading/memory/`).

### Bug kinh điển đã dính — ĐỪNG lặp lại
1. **Bot câm nhiều tuần** vì get_top_signals fallback trả signal test không tồn tại → giờ trả `[]` để bootstrap. Đừng thêm fallback "trả bừa" kiểu đó nữa.
2. **H1 trend bị NGƯỢC** (RSI<50 = UP?!) ở 2 chỗ suốt 1 tháng — sửa 1 chỗ thì grep các chỗ còn lại.
3. **Runtime json từng nằm trong git** → deploy đè mất data VPS. Đã .gitignore. Đừng commit lại trades.json/learning.json/alert_tracker.json/trading_profile.json.
4. **P&L SELL ngược dấu** trong close_alert (thiếu nhân -1) — đã fix, để ý khi thêm công thức P&L mới.
5. **Chạy bot local = 409 Conflict** với VPS. Test bằng cách gọi hàm trực tiếp, không chạy `python telegram_bot_v2.py`.

### TODO còn treo (ưu tiên từ trên xuống)
- [ ] Learning theo cặp (signal + symbol) — hiện gộp XAU/BTC chung 1 rổ, P&L khác scale làm méo avg_win/RRR
- [ ] Hạ MIN_TRADES_PER_SIGNAL 5 → 3 hoặc bơm data backtest vào learning (cold-start chậm: 8 signals × 5 trades mới có confidence)
- [ ] Thống kê TP level nào hit nhiều nhất per signal → gợi ý "signal X nên chốt TP1"
- [ ] Backtest thêm slippage/spread; backtest khung 5m (hiện chỉ 15m)
- [ ] TradingEconomics API cho lịch kinh tế thật (macro_analysis.py đang hardcode)
- [ ] Auto-trade execution (Oanda V20...) — user CHƯA muốn, hỏi lại trước khi làm

---

## 9. Reference

### Telegram
```
Bot Token:  8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY
Channel:    @Zion_XAU_Signals (public)
Personal:   ID 1085188912
```

### Data Source (Phase 9 update)
- **Primary:** `tvDatafeed` — TradingView realtime data (no delay)
  - XAU → `OANDA:XAUUSD` · XAG → `OANDA:XAGUSD`
  - BTC → `COINBASE:BTCUSD` · ETH → `COINBASE:ETHUSD`
  - USOIL → `TVC:USOIL` · DXY → `TVC:DXY`
- **Fallback:** yfinance (if tvDatafeed import fails)
  - ⚠️ yfinance `GC=F` (Gold Futures) bị delay 15-30 min trên free tier
  - ⚠️ yfinance KHÔNG hỗ trợ intraday 5m cho Forex pairs (`XAUUSD=X` fail với `interval='5m'`)

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
- **2026-05-22 Phase 5:** Fibonacci retracement + rejection candle confluence detection
- **2026-05-22 Phase 6:** Three TP levels (127.2% / 161.8% / 200%) with per-level tracking
- **2026-05-22 Phase 7:** Trading profile learning system (/teach, /mystyle, /trades-taught)
- **2026-05-22 Phase 8:** Macro economic analysis (daily reports + pre-event alerts)
- **2026-05-23 Production deploy:** Setup VPS DigitalOcean Singapore, systemd service, 24/7 running
- **2026-06-09 Phase 9 (debug + reliability):**
  - Fix 409 Conflict (laptop bot vs VPS bot — instructed user to kill laptop process)
  - Fix BUY_TEST infinite skip (DEFAULT_SIGNALS bootstrap when learning empty)
  - SL clamp per-symbol (XAU 100-150 pip)
  - Volume threshold 1.2x → 0.8x + auto-pass for Forex (no volume)
  - tvDatafeed integration (realtime XAU from TradingView, fallback yfinance)
- **2026-07-07 (sáng — debug bot câm):**
  - Root cause thật của bot câm: get_top_signals fallback trả BUY_TEST → không match setup nào (commit 4c91c58)
  - Untrack runtime json + .venv + __pycache__ khỏi git, thêm .gitignore (cc4adc3)
  - Session map fix: ASIAN = 0-8 UTC (7h-15h VN), bỏ gate conf>=75 phiên Á; OVERNIGHT chỉ còn 22-0 UTC (cc4adc3)
  - Fix H1 trend NGƯỢC trong alert filter (BUY chỉ pass khi H1 giảm!) + /h1 hiển thị ngược (ff3ce33)
- **2026-07-07 Phase 10 (SMC Overhaul):** Thay toàn bộ hệ signal bằng SMC (BOS/CHoCH + OB/FVG + nến Nhật) + Elliott H4 bias. Chỉ đánh XAU + BTC. 4 module mới: smc_structure, candle_patterns, elliott_wave, smc_check. fetch.py thêm khung 4h (yfinance fallback resample từ 1h).
