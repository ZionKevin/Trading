# -*- coding: utf-8 -*-
"""Phân tích trend, momentum, volatility từ indicator set."""
import pandas as pd
from indicators import IndicatorSet


class Analysis:
    """Analyze trend/momentum/volatility từ IndicatorSet."""

    def __init__(self, ind_set, symbol="BTC", timeframe="1h"):
        """
        Args:
            ind_set: IndicatorSet object (đã calculate_all())
            symbol: "BTC", "ETH", "XAU", ...
            timeframe: "1h", "4h", "1d"
        """
        self.ind = ind_set
        self.symbol = symbol
        self.timeframe = timeframe
        self.df = ind_set.df

    def trend_direction(self):
        """Phân tích xu hướng: UP / DOWN / NEUTRAL.

        Returns:
            dict: {'direction': 'UP'/'DOWN', 'strength': 1-10, 'reason': str}
        """
        ema20 = self.ind.latest('ema20')
        ema50 = self.ind.latest('ema50')
        st_trend = self.ind.latest('supertrend_trend')
        close = self.df['Close'].iloc[-1]

        # Alignment check
        up_count = 0
        reasons = []

        if close > ema20:
            up_count += 1
            reasons.append("Close > EMA20")
        if ema20 > ema50:
            up_count += 1
            reasons.append("EMA20 > EMA50")
        if st_trend == 1:
            up_count += 1
            reasons.append("SuperTrend UP")

        if up_count >= 2:
            direction = "UP"
            strength = min(10, 5 + up_count * 2)
        elif up_count == 0:
            direction = "DOWN"
            strength = min(10, 5 + (3 - up_count) * 2)
        else:
            direction = "NEUTRAL"
            strength = 5

        return {
            'direction': direction,
            'strength': strength,
            'reasons': reasons
        }

    def momentum_strength(self):
        """Phân tích momentum: STRONG / MODERATE / WEAK.

        Returns:
            dict: {'level': str, 'rsi': float, 'macd_signal': str}
        """
        rsi = self.ind.latest('rsi')
        macd_hist = self.ind.latest('macd_hist')
        macd_signal = self.ind.latest('macd_signal')

        # RSI interpretation
        if rsi > 70:
            rsi_signal = "OB"  # Overbought
        elif rsi < 30:
            rsi_signal = "OS"  # Oversold
        elif rsi > 60:
            rsi_signal = "STRONG"
        elif rsi < 40:
            rsi_signal = "WEAK"
        else:
            rsi_signal = "NEUTRAL"

        # MACD signal
        if macd_hist > 0:
            macd_status = "BULLISH"
        else:
            macd_status = "BEARISH"

        # Combined level
        if rsi_signal in ["OB", "OS"]:
            level = "EXTREME"
        elif rsi_signal in ["STRONG", "WEAK"]:
            level = "STRONG"
        else:
            level = "MODERATE"

        return {
            'level': level,
            'rsi': round(rsi, 2),
            'rsi_signal': rsi_signal,
            'macd_status': macd_status
        }

    def volatility_profile(self):
        """Phân tích volatility: HIGH / MEDIUM / LOW.

        Returns:
            dict: {'level': str, 'atr': float, 'bb_width': float}
        """
        atr = self.ind.latest('atr')
        close = self.df['Close'].iloc[-1]
        atr_pct = (atr / close) * 100

        bb_high = self.ind.latest('bb_high')
        bb_low = self.ind.latest('bb_low')
        bb_width = (bb_high - bb_low) / close * 100

        if atr_pct > 2.0 or bb_width > 5.0:
            level = "HIGH"
        elif atr_pct > 1.0 or bb_width > 2.5:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            'level': level,
            'atr': round(atr, 2),
            'atr_pct': round(atr_pct, 3),
            'bb_width_pct': round(bb_width, 3)
        }

    def key_levels(self):
        """Mức support/resistance quan trọng.

        Returns:
            dict: {'support': [s1,s2], 'resistance': [r1,r2], 'pivot': float}
        """
        pivot = self.ind.latest('pivot')
        r1 = self.ind.latest('r1')
        r2 = self.ind.latest('r2')
        s1 = self.ind.latest('s1')
        s2 = self.ind.latest('s2')

        return {
            'pivot': round(pivot, 2),
            'resistance': [round(r1, 2), round(r2, 2)],
            'support': [round(s1, 2), round(s2, 2)]
        }

    def ma34_89_alignment(self):
        """Kiểm tra MA34/89 alignment (bullish/bearish).

        Returns:
            dict: {'alignment': 'BULLISH'/'BEARISH'/'NEUTRAL', 'ma34_close': f, 'ma89_close': f}
        """
        close = self.df['Close'].iloc[-1]
        ma34_c = self.ind.latest('ma34_close')
        ma34_h = self.ind.latest('ma34_high')
        ma34_l = self.ind.latest('ma34_low')
        ma89_c = self.ind.latest('ma89_close')

        # Bullish alignment: Close > MA34(close) > MA34(low), MA34(close) > MA89
        bullish = close > ma34_c and ma34_c > ma34_l and ma34_c > ma89_c
        bearish = close < ma34_c and ma34_c < ma34_h and ma34_c < ma89_c

        if bullish:
            alignment = "BULLISH"
        elif bearish:
            alignment = "BEARISH"
        else:
            alignment = "NEUTRAL"

        return {
            'alignment': alignment,
            'ma34_close': round(ma34_c, 2),
            'ma89_close': round(ma89_c, 2),
            'price': round(close, 2)
        }

    def dow_analysis(self):
        """Phân tích Dow Theory.

        Returns:
            dict: trend, reversal signal, key levels
        """
        trend = self.ind.latest('dow_trend')
        hh = self.ind.latest('dow_last_hh')
        hl = self.ind.latest('dow_last_hl')
        ll = self.ind.latest('dow_last_ll')
        lh = self.ind.latest('dow_last_lh')
        reversal = self.ind.latest('dow_reversal')

        return {
            'trend': trend,
            'reversal_signal': reversal,
            'last_hh': round(hh, 2) if hh else None,
            'last_hl': round(hl, 2) if hl else None,
            'last_ll': round(ll, 2) if ll else None,
            'last_lh': round(lh, 2) if lh else None
        }

    def summary(self):
        """Trả toàn bộ analysis summary."""
        trend = self.trend_direction()
        momentum = self.momentum_strength()
        volatility = self.volatility_profile()
        levels = self.key_levels()
        ma_alignment = self.ma34_89_alignment()
        dow = self.dow_analysis()
        close = round(self.df['Close'].iloc[-1], 2)

        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timestamp': str(self.df.index[-1]),
            'close': close,
            'trend': trend,
            'momentum': momentum,
            'volatility': volatility,
            'levels': levels,
            'ma34_89': ma_alignment,
            'dow': dow
        }

    def text_report(self):
        """Output text report."""
        summary = self.summary()
        trend = summary['trend']
        momentum = summary['momentum']
        vol = summary['volatility']
        levels = summary['levels']
        ma = summary['ma34_89']
        dow = summary['dow']

        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"{summary['symbol']} {summary['timeframe']} - {summary['timestamp']}")
        lines.append(f"{'='*60}")
        lines.append(f"Price: ${summary['close']:,.2f}")
        lines.append("")

        # DOW Theory
        lines.append(f"DOW THEORY: {dow['trend']}")
        if dow['reversal_signal']:
            lines.append(f"  ⚠️ REVERSAL SIGNAL DETECTED")
        if dow['last_hh']:
            lines.append(f"  Last HH: ${dow['last_hh']:,.2f} | Last HL: ${dow['last_hl']:,.2f}")
        if dow['last_ll']:
            lines.append(f"  Last LL: ${dow['last_ll']:,.2f} | Last LH: ${dow['last_lh']:,.2f}")
        lines.append("")

        # MA34/89 Alignment
        lines.append(f"MA34/89 ALIGNMENT: {ma['alignment']}")
        lines.append(f"  MA34(Close): ${ma['ma34_close']:,.2f}")
        lines.append(f"  MA89(Close): ${ma['ma89_close']:,.2f}")
        lines.append("")

        lines.append(f"TREND: {trend['direction']} (strength: {trend['strength']}/10)")
        lines.append(f"  {', '.join(trend['reasons'])}")
        lines.append("")
        lines.append(f"MOMENTUM: {momentum['level']} (RSI: {momentum['rsi']}, {momentum['rsi_signal']})")
        lines.append(f"  MACD: {momentum['macd_status']}")
        lines.append("")
        lines.append(f"VOLATILITY: {vol['level']} (ATR: {vol['atr_pct']}%)")
        lines.append("")
        lines.append(f"KEY LEVELS:")
        lines.append(f"  R2: ${levels['resistance'][1]:,.2f}")
        lines.append(f"  R1: ${levels['resistance'][0]:,.2f}")
        lines.append(f"  Pivot: ${levels['pivot']:,.2f}")
        lines.append(f"  S1: ${levels['support'][0]:,.2f}")
        lines.append(f"  S2: ${levels['support'][1]:,.2f}")

        return "\n".join(lines)
