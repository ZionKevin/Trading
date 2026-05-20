# -*- coding: utf-8 -*-
"""Tính indicator cho trading analysis."""
import pandas as pd
import ta
import numpy as np


class IndicatorSet:
    """Wrapper tính tất cả indicator từ 1 OHLCV dataframe."""

    def __init__(self, df):
        """
        Args:
            df: pd.DataFrame với columns ['Open','High','Low','Close','Volume'], index=datetime
        """
        self.df = df.copy()
        self.indicators = {}

    def calculate_all(self):
        """Tính hết tất cả indicator."""
        self.ema(20, 50, 200)
        self.sma(20, 50, 200)
        self.rsi(14)
        self.macd(12, 26, 9)
        self.atr(14)
        self.bollinger(20, 2)
        self.vwap()
        self.pvt()
        self.supertrend(10, 3)
        self.pivot_points()
        self.ma_34_89()
        self.dow_theory()
        return self

    def ema(self, *windows):
        """EMA."""
        for w in windows:
            self.indicators[f'ema{w}'] = ta.trend.ema_indicator(self.df['Close'], w)

    def sma(self, *windows):
        """SMA."""
        for w in windows:
            self.indicators[f'sma{w}'] = ta.trend.sma_indicator(self.df['Close'], w)

    def rsi(self, window=14):
        """RSI."""
        self.indicators['rsi'] = ta.momentum.rsi(self.df['Close'], window)

    def macd(self, fast=12, slow=26, signal=9):
        """MACD."""
        macd_line = ta.trend.macd(self.df['Close'], fast, slow)
        signal_line = ta.trend.macd_signal(self.df['Close'], fast, slow, signal)
        hist = macd_line - signal_line
        self.indicators['macd'] = macd_line
        self.indicators['macd_signal'] = signal_line
        self.indicators['macd_hist'] = hist

    def atr(self, window=14):
        """ATR."""
        self.indicators['atr'] = ta.volatility.average_true_range(
            self.df['High'], self.df['Low'], self.df['Close'], window)

    def bollinger(self, window=20, std=2):
        """Bollinger Bands."""
        bb = ta.volatility.BollingerBands(self.df['Close'], window, std)
        self.indicators['bb_high'] = bb.bollinger_hband()
        self.indicators['bb_mid'] = bb.bollinger_mavg()
        self.indicators['bb_low'] = bb.bollinger_lband()

    def vwap(self):
        """VWAP = Σ(TP * Volume) / Σ Volume."""
        tp = (self.df['High'] + self.df['Low'] + self.df['Close']) / 3
        cum_tp_vol = (tp * self.df['Volume']).cumsum()
        cum_vol = self.df['Volume'].cumsum()
        self.indicators['vwap'] = cum_tp_vol / cum_vol

    def pvt(self):
        """Price Volume Trend."""
        self.indicators['pvt'] = ta.volume.VolumePriceTrendIndicator(
            self.df['Close'], self.df['Volume']).volume_price_trend()

    def supertrend(self, window=10, mult=3):
        """SuperTrend: tính BaseLine + ATR band, track trend."""
        hl = (self.df['High'] + self.df['Low']) / 2
        hl_sma = hl.rolling(window).mean()
        atr = ta.volatility.average_true_range(
            self.df['High'], self.df['Low'], self.df['Close'], window)

        upper = hl_sma + mult * atr
        lower = hl_sma - mult * atr

        st = pd.Series(index=self.df.index, dtype=float)
        trend = pd.Series(index=self.df.index, dtype=int)

        for i in range(window, len(self.df)):
            if i == window:
                st.iloc[i] = upper.iloc[i]
                trend.iloc[i] = -1
            else:
                if trend.iloc[i - 1] == 1:
                    lower.iloc[i] = max(lower.iloc[i], lower.iloc[i - 1])
                    if self.df['Close'].iloc[i] <= lower.iloc[i]:
                        trend.iloc[i] = -1
                        st.iloc[i] = upper.iloc[i]
                    else:
                        trend.iloc[i] = 1
                        st.iloc[i] = lower.iloc[i]
                else:
                    upper.iloc[i] = min(upper.iloc[i], upper.iloc[i - 1])
                    if self.df['Close'].iloc[i] >= upper.iloc[i]:
                        trend.iloc[i] = 1
                        st.iloc[i] = lower.iloc[i]
                    else:
                        trend.iloc[i] = -1
                        st.iloc[i] = upper.iloc[i]

        self.indicators['supertrend'] = st
        self.indicators['supertrend_trend'] = trend

    def pivot_points(self):
        """Pivot Points chuẩn."""
        pv = (self.df['High'] + self.df['Low'] + self.df['Close']) / 3
        hl_range = self.df['High'] - self.df['Low']

        self.indicators['pivot'] = pv
        self.indicators['r1'] = 2 * pv - self.df['Low']
        self.indicators['s1'] = 2 * pv - self.df['High']
        self.indicators['r2'] = pv + hl_range
        self.indicators['s2'] = pv - hl_range
        self.indicators['r3'] = self.df['High'] + 2 * (pv - self.df['Low'])
        self.indicators['s3'] = self.df['Low'] - 2 * (self.df['High'] - pv)

    def ma_34_89(self):
        """MA34 + MA89 (mục đích Dow + alignment)."""
        # MA34 từ Close, High, Low riêng
        self.indicators['ma34_close'] = ta.trend.ema_indicator(self.df['Close'], 34)
        self.indicators['ma34_high'] = ta.trend.ema_indicator(self.df['High'], 34)
        self.indicators['ma34_low'] = ta.trend.ema_indicator(self.df['Low'], 34)

        # MA89 từ Close
        self.indicators['ma89_close'] = ta.trend.ema_indicator(self.df['Close'], 89)

    def dow_theory(self, lookback=50):
        """Dow Theory: phát hiện HH/HL (uptrend) vs LL/LH (downtrend).

        Args:
            lookback: số candles gần nhất để tìm swing points

        Returns dict với:
          - current_trend: 'UP', 'DOWN', 'UNKNOWN'
          - last_hh, last_hl, last_ll, last_lh: giá + bar number
          - reversal_signal: True nếu break HL (uptrend) hoặc LH (downtrend)
        """
        lows = self.df['Low'].tail(lookback)
        highs = self.df['High'].tail(lookback)

        # Tìm swing points
        swing_lows = []
        swing_highs = []

        for i in range(1, len(lows) - 1):
            if lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i+1]:
                swing_lows.append((i, lows.iloc[i]))
            if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i+1]:
                swing_highs.append((i, highs.iloc[i]))

        # Phát hiện trend
        trend = "UNKNOWN"
        last_hh = last_hl = last_ll = last_lh = None
        reversal_signal = False

        if len(swing_highs) >= 2:
            hh_check = swing_highs[-1][1] > swing_highs[-2][1]
        else:
            hh_check = False

        if len(swing_lows) >= 2:
            hl_check = swing_lows[-1][1] > swing_lows[-2][1]
            ll_check = swing_lows[-1][1] < swing_lows[-2][1]
            lh_check = swing_highs[-1][1] < swing_highs[-2][1] if len(swing_highs) >= 2 else False
        else:
            hl_check = ll_check = lh_check = False

        # Determine trend
        if hh_check and hl_check:
            trend = "UP"
            last_hh = swing_highs[-1][1]
            last_hl = swing_lows[-1][1]
        elif ll_check and lh_check:
            trend = "DOWN"
            last_ll = swing_lows[-1][1]
            last_lh = swing_highs[-1][1]

        # Check reversal: break HL (uptrend) hoặc LH (downtrend)
        close = self.df['Close'].iloc[-1]
        if trend == "UP" and last_hl and close < last_hl:
            reversal_signal = True
        elif trend == "DOWN" and last_lh and close > last_lh:
            reversal_signal = True

        # Store as Series (repeat for all rows) để consistent với get/latest
        self.indicators['dow_trend'] = pd.Series(trend, index=self.df.index)
        self.indicators['dow_last_hh'] = pd.Series(last_hh if last_hh else 0, index=self.df.index)
        self.indicators['dow_last_hl'] = pd.Series(last_hl if last_hl else 0, index=self.df.index)
        self.indicators['dow_last_ll'] = pd.Series(last_ll if last_ll else 0, index=self.df.index)
        self.indicators['dow_last_lh'] = pd.Series(last_lh if last_lh else 0, index=self.df.index)
        self.indicators['dow_reversal'] = pd.Series(reversal_signal, index=self.df.index)

    def get(self, indicator_name):
        """Lấy Series của 1 indicator."""
        if indicator_name not in self.indicators:
            raise ValueError(f"Indicator '{indicator_name}' chưa calculated")
        return self.indicators[indicator_name]

    def latest(self, indicator_name):
        """Lấy giá trị cuối cùng của 1 indicator."""
        return self.get(indicator_name).iloc[-1]

    def all_latest(self):
        """Trả dict tất cả indicator + giá trị cuối."""
        result = {}
        for name, series in self.indicators.items():
            result[name] = series.iloc[-1]
        return result
