# Trading Analysis Tool

Công cụ phân tích thị trường tự động cho 6 symbol: **BTC, ETH, XAU, XAG, USOIL, DXY**

## Setup

```bash
cd C:\Projects\Trading
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Cách dùng

### Mode 1: Daily Report (tất cả 6 symbol daily)

**Text format:**
```bash
python report.py
```

**CSV format (export):**
```bash
python report.py --csv -o daily_report.csv
```

### Mode 2: On-demand (1 symbol, custom timeframe)

```bash
python report.py BTC -t 1h       # BTC 1h
python report.py ETH -t 4h       # ETH 4h
python report.py XAU -t 1d       # XAU daily
```

Timeframe support: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`

## Output

### Text Report
```
BTC 1h - [timestamp]
=========================================
Price: $77,500.00

TREND: UP (strength: 9/10)
  Close > EMA20, EMA20 > EMA50

MOMENTUM: MODERATE (RSI: 59.37, NEUTRAL)
  MACD: BEARISH

VOLATILITY: LOW (ATR: 0.486%)

KEY LEVELS:
  R2: $78,060.06
  R1: $77,792.83
  Pivot: $77,507.42
  S1: $77,240.19
  S2: $76,954.78
```

### CSV Format
```csv
timestamp,symbol,price,trend,trend_strength,momentum,rsi,volatility,pivot,r1,s1
2026-05-20 08:43 UTC,BTC,"$77,364.72",UP,9,MODERATE,47.0,HIGH,"$77,147.20","$77,795.12","$76,716.80"
```

## Indicator Set

10 indicator tính tự động:

| Indicator | Mục đích |
|-----------|---------|
| **EMA 20/50/200** | Trend direction + alignment |
| **SMA 20/50/200** | Trend confirmation |
| **RSI(14)** | Momentum + overbought/oversold |
| **MACD(12,26,9)** | Trend + momentum signal |
| **SuperTrend(10,3)** | Support/resistance dynamic |
| **ATR(14)** | Volatility + stop loss distance |
| **Bollinger Bands(20,2)** | Volatility level + squeeze |
| **VWAP** | Volume-weighted average price |
| **PVT** | Price-volume trend |
| **Pivot Points** | Daily S/R levels (R2, R1, S1, S2) |

## Analysis Output

Mỗi symbol được phân tích theo 4 layer:

1. **TREND** (UP/DOWN/NEUTRAL)
   - EMA alignment (20 > 50 > 200?)
   - SuperTrend direction
   - Strength rating 1-10

2. **MOMENTUM** (STRONG/MODERATE/WEAK/EXTREME)
   - RSI level + signal (OB/OS/STRONG/WEAK/NEUTRAL)
   - MACD bullish/bearish

3. **VOLATILITY** (HIGH/MEDIUM/LOW)
   - ATR % of price
   - Bollinger Band width %

4. **KEY LEVELS**
   - Pivot, R1, R2, S1, S2
   - Entry/exit reference

## Data Source

- **BTC, ETH**: yfinance (BTC-USD, ETH-USD) — 1m to 1d
- **XAU (Gold)**: yfinance (GC=F) — daily
- **XAG (Silver)**: yfinance (SI=F) — daily
- **USOIL (Crude Oil)**: yfinance (CL=F) — daily
- **DXY (US Dollar Index)**: yfinance (DX-Y.NYB) — daily

## Architecture

```
fetch.py          → Fetch OHLCV từ yfinance
  ↓
indicators.py     → Tính 10 indicator
  ↓
analyze.py        → Trend/momentum/volatility analysis
  ↓
report.py         → CLI interface (daily/on-demand)
```

## Note

- Binance API bị geo-block từ VN → dùng yfinance thay (free, realtime OK)
- EMA200 có thể NaN nếu data chưa đủ 200 nến — bình thường
- CSV export auto-quay vòng (giữ theo ngày)

## Next Steps

- (Optional) Setup Windows scheduled task để chạy daily 8am
- (Optional) Build Pine Script v5 cho TradingView alerts (Prompt 4)
- (Ready) Dùng report output làm input cho AI trading analysis (Prompts 1-3)
