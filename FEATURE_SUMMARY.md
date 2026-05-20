# XAU Scalp Trading Bot — Complete Feature Summary

## 1. All Features & Current Status

| Feature | Status | Phase |
|---------|--------|-------|
| XAU scalp signals (M5/M15) | ✅ | 1 |
| Daily technical analysis | ✅ | 1 |
| Trade logging + P&L tracking | ✅ | 1 |
| Telegram bot polling | ✅ | 1 |
| Volume + Consolidation filters | ✅ | 2 |
| Smart alerts (no spam) | ✅ | 2 |
| Multi-symbol (6 symbols) | ✅ | 3 |
| Daily stats report (7 PM) | ✅ | 3 |
| Backtesting (30 days) | 🔄 | 4 |
| Self-learning framework | ⏳ | 5 |
| Trend filtering (H1 align) | ⏳ | 5 |
| Dynamic SL/TP (ATR-based) | ⏳ | 5 |
| Auto-trade execution | ⏳ | 6 |

---

## 2. All Commands (Telegram)

### Market Analysis Commands
```
/price    → Current prices (XAU, BTC, ETH, XAG, USOIL, DXY) + RSI + trend direction
/trend    → H1 macro trend per symbol (UP/DOWN/NEUTRAL based on RSI)
/status   → Market overview (volatility, key levels, pivot points, support/resistance)
/h1       → H1 trend confirmation (macro direction check)
```

### Scalp Analysis Commands
```
/m5       → M5 setup analysis for XAU
            Shows: Direction, Current price, Entry level, SL, TP
            Action: "Wait for bounce to X" or "Enter on break above Y"
            Volume & consolidation status
            
/m15      → M15 setup analysis for XAU (same as M5 format)
```

### Trade Management Commands
```
/enter SIGNAL_NAME PRICE
  Example: /enter BUY_PIVOT_S1_BOUNCE 4550.00
  → Logs trade entry, assigns auto-increment ID
  → Default lot: 0.2 (can customize)
  
/close PRICE
  Example: /close 4560.00
  → Auto-finds last OPEN trade
  → Calculates P&L: (exit - entry) × $10 × lot_size
  → Updates trade status to CLOSED
  → Shows: Entry, Exit, P&L amount
  
/stats
  → All-time trade statistics
  → Win rate %, RRR (risk/reward ratio)
  → Average win/loss per trade
  → Total P&L
  → Per-signal breakdown (which signals win most)
  
/trades
  → Recent 10 trades (ID, signal, entry→exit, status)
  → OPEN trades show "OPEN", CLOSED show P&L amount
```

---

## 3. All Signal Types (10 Total)

### Bounce Signals (6)
| Signal | Trigger | Best For | Risk |
|--------|---------|----------|------|
| BUY_MA89_BOUNCE | Price touches EMA89(Close) ±2 pips from below | Mean reversion | Medium |
| BUY_SUPPORT_BOUNCE | Price touches recent support (recent 15 candles) | Support bounce | Medium |
| BUY_PIVOT_S1_BOUNCE | Price touches pivot point S1 | Classical pivot | High confidence |
| SELL_RESISTANCE_BOUNCE | Price touches recent resistance (recent 15 candles) | Resistance bounce | Medium |
| SELL_PIVOT_R1_BOUNCE | Price touches pivot point R1 | Classical pivot | High confidence |
| SELL_MA89_BOUNCE | Price touches EMA89(Close) ±2 pips from above | Mean reversion | Medium |

### Breakout Signals (4)
| Signal | Trigger | Best For | Risk |
|--------|---------|----------|------|
| BUY_TRENDLINE_BREAKUP | Break above uptrend trendline (higher lows pattern) | Trend continuation | Low (confirmation) |
| BUY_SUPPORT_BREAK | Strong break below support (−3 pips minimum) | Breakout scalp | High (false breakout risk) |
| SELL_TRENDLINE_BREAKDN | Break below downtrend trendline (lower highs pattern) | Trend continuation | Low (confirmation) |
| SELL_RESISTANCE_BREAK | Strong break above resistance (+3 pips minimum) | Breakout scalp | High (false breakout risk) |

---

## 4. Phase 2 Filters (Smart Alert Conditions)

### Alert Posts ONLY if BOTH TRUE:
```
volume_is_strong = current_volume > 120% of 20-day average
AND
is_consolidating = current_ATR < 70% of 20-day average ATR
```

### Why This Works
- **High volume:** Confirms breakout is real (not noise)
- **Low ATR (consolidating):** Setup is clean, tight range before move
- **Together:** Indicates "coiled spring" setup — low volatility before big move

### Without These Filters
- False breakouts (volume weak) → lose money
- Trending noise (ATR high) → whipsawed in and out
- Too many alerts (alert fatigue) → user ignores real setups

---

## 5. Trading Methods & Risk Management

### Scalp Method
```
Entry:    Bounce off support/MA/pivot OR breakout with volume
SL:       6 pips (fixed, can tune)
TP:       10 pips (fixed, can tune)
Risk:     $60 per trade (6 pips × $10 × 0.2 lot)
Profit:   $200 per trade (10 pips × $10 × 0.2 lot)
RR Ratio: 1:3.33 (win $200 for every $60 risked)
Timeframe: M5/M15 (hold 15 min - 2 hours typical)
```

### Symbol-Specific Adjustments (TODO)
```
XAU:   SL 6, TP 10 (typical, tight range)
BTC:   SL ? TP ? (more volatile, needs test)
ETH:   SL ? TP ? (more volatile, needs test)
USOIL: SL ? TP ? (crude oil, wide swings)
```

### Position Sizing
```
Default: 0.2 lot per trade (can override in /enter)
Max per trade: 0.5 lot (risk limit)
Daily max: $1000 total risk (10 trades × $100 max)
Win rate target: 55%+ (with Phase 2 filters should achieve)
```

### Time Selection (Optimal Hours)
```
Best (TBD from backtest + learning):
  - TBD (run backtest to identify)
Worst (TBD from backtest + learning):
  - TBD (skip these hours)
Caveat: Different hours for each symbol (BTC vs XAU different volumes)
```

---

## 6. Multi-Symbol Support (6 Symbols)

| Symbol | Full Name | Emoji | Ticker | Volatility | Best Timeframe |
|--------|-----------|-------|--------|------------|-----------------|
| XAU | Gold | 🥇 | GC=F | Low | 5m/15m |
| BTC | Bitcoin | 🔵 | BTC-USD | High | 15m |
| ETH | Ethereum | ⬜ | ETH-USD | High | 15m |
| XAG | Silver | 🪙 | SI=F | Medium | 5m |
| USOIL | Crude Oil | 🛢️ | CL=F | High | 15m |
| DXY | Dollar Index | 💹 | DX-Y.NYB | Medium | 15m |

### Current Setup
- All 6 symbols checked every 5 minutes (M5 + M15)
- Independent alert cooldown per symbol+timeframe
- Same Phase 2 filters (volume + consolidation)

### Future Tuning
- [ ] XAU: fine-tune SL/TP (tight range)
- [ ] BTC: wider SL/TP (high volatility)
- [ ] ETH: similar to BTC tuning
- [ ] USOIL: crude volatility pattern (different from metals)
- [ ] DXY: macroeconomic driver (trade with USD weakness/strength)

---

## 7. Daily Report (Auto 7 PM)

### Report Contents
```
TRADE STATS (Today)
Total: X | Open: Y | Closed: Z
Win Rate: A% | RRR: B
Avg Win: $C | Avg Loss: $D
Total P&L: $E

By Signal:
  BUY_PIVOT_S1_BOUNCE: 2W-0L (100%) | $400
  SELL_RESISTANCE_BOUNCE: 1W-1L (50%) | $100
  ...

Alerts Posted: N
```

### What to Look For Daily
- Win rate < 50%? → Might have losing streak, check signals quality
- Win rate > 65%? → Good setup, keep alert conditions
- P&L negative? → Stop trading, review recent losses
- Alerts < 5/day? → Market quiet, reduced opportunity
- Alerts > 20/day? → Might be too loose filters, increase volume/consolidation threshold

---

## 8. Backtesting Output (Phase 4)

### What Backtest Measures
```
Per symbol + signal type:
  - Win rate %
  - Avg win/loss $
  - RRR ratio
  - Max consecutive wins/losses
  - Total P&L on 30-day historical data
  - Max drawdown (biggest underwater period)
  - Sharpe ratio (risk-adjusted return)

Example:
  BUY_PIVOT_S1_BOUNCE (XAU M5):
    - 32 total trades, 22 wins, 10 losses
    - Win rate: 68.75%
    - Avg win: $185, Avg loss: $75
    - RRR: 2.47
    - Total P&L: +$2,950
    - Max DD: -$420
```

### Use Backtesting Results
- Validate signal quality before trading live
- Compare win rates: which signals to trust most?
- Identify symbols to avoid (low win rate)
- Optimize SL/TP: backtest with different values, find best

---

## 9. What's Missing (Phase 5+)

### High Priority
- [ ] **Self-learning:** Track which signals work, auto-optimize
- [ ] **Trend filter:** Only BUY when H1=UP, only SELL when H1=DOWN
- [ ] **Time-of-day:** Identify best trading hours, skip bad hours
- [ ] **Dynamic SL/TP:** Base on ATR instead of fixed

### Medium Priority
- [ ] **Symbol performance:** Rank symbols by win rate, alert best ones first
- [ ] **Consecutive wins/losses:** Detect hot/cold streaks
- [ ] **Commission modeling:** Backtest with realistic slippage
- [ ] **Real-time dashboard:** Show live P&L, win rate in Telegram

### Low Priority
- [ ] **Auto-trade execution:** Connect to broker API (Oanda/etc)
- [ ] **Mobile app:** Custom UI instead of just Telegram
- [ ] **Machine learning:** Predict win probability before entry

---

## 10. Summary Table — What You Have vs What's Missing

| Aspect | Have | Missing | Priority |
|--------|------|---------|----------|
| Signals | 10 types ✅ | ML ranking | Medium |
| Symbols | 6 symbols ✅ | Per-symbol tuning | Medium |
| Alerts | Smart filters ✅ | Trend align | High |
| Trade logging | Full ✅ | - | - |
| Daily stats | Yes ✅ | Real-time | Low |
| Backtesting | 30-day ✅ | ML model | Low |
| Self-learning | Framework only ⏳ | Full impl | High |
| Risk mgmt | Basic ✅ | Dynamic SL/TP | Medium |
| Execution | Manual ✅ | Auto | Low |

---

## 11. How to Extend (Next Steps for You)

### To Add Trend Filtering
1. Get H1 RSI for each symbol
2. Only BUY if H1_RSI < 50 (uptrend)
3. Only SELL if H1_RSI > 50 (downtrend)
4. Implement in `smart_alert_loop()` before posting

### To Add Self-Learning
1. Enrich trade logging with context (H1 trend, volume%, hour)
2. Create `learning.py` to analyze per-signal win rate
3. Auto-generate recommendations daily
4. Implement feedback: user can say "disable BTC" → bot learns

### To Add Dynamic SL/TP
1. Calculate ATR for each symbol (already have in code)
2. Set SL = entry ± ATR, TP = entry ± 2×ATR
3. Backtest new values, compare to fixed 6/10
4. Deploy per-symbol if better

---

## Edit Log
- 2026-05-20: Initial feature summary (Phase 1-4 complete, Phase 5 TODO)
