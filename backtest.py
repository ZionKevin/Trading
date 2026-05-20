# -*- coding: utf-8 -*-
"""Backtest scalp signals on 30 days historical data."""
import pandas as pd
from fetch import fetch_symbol
from scalp_check import find_scalp_entry, check_volume_strength, check_consolidation
from datetime import datetime, timedelta
import numpy as np


def backtest_symbol(symbol, timeframe="5m", days=30):
    """Backtest scalp signals for a symbol on historical data.

    Args:
        symbol: 'XAU', 'BTC', 'ETH', etc.
        timeframe: '5m' or '15m'
        days: lookback days

    Returns:
        dict with backtest results
    """
    try:
        df = fetch_symbol(symbol, timeframe, days)
        if len(df) < 100:
            return None

        trades = []
        i = 0
        while i < len(df):
            # Check for setup at this bar
            df_window = df.iloc[:i+1].copy()
            df_h1 = fetch_symbol(symbol, "1h", 5)

            setup = find_scalp_entry(df_window, symbol, df_h1)

            if setup and setup['volume_is_strong'] and setup['is_consolidating']:
                entry_price = setup['entry']
                sl_price = setup['sl']
                tp_price = setup['tp']
                signal = setup['signal']
                entry_time = df.index[i]

                # Simulate trade from next bar
                is_buy = "BUY" in signal
                trade_open = True
                exit_price = None
                exit_time = None
                pnl = None

                for j in range(i+1, len(df)):
                    high = df['High'].iloc[j]
                    low = df['Low'].iloc[j]
                    close = df['Close'].iloc[j]

                    # Check exit conditions
                    if is_buy:
                        if low <= sl_price:  # Hit SL
                            exit_price = sl_price
                            pnl = (sl_price - entry_price) * 10
                            exit_time = df.index[j]
                            trade_open = False
                            break
                        elif high >= tp_price:  # Hit TP
                            exit_price = tp_price
                            pnl = (tp_price - entry_price) * 10
                            exit_time = df.index[j]
                            trade_open = False
                            break
                    else:  # SELL
                        if high >= sl_price:  # Hit SL
                            exit_price = sl_price
                            pnl = (entry_price - sl_price) * 10
                            exit_time = df.index[j]
                            trade_open = False
                            break
                        elif low <= tp_price:  # Hit TP
                            exit_price = tp_price
                            pnl = (entry_price - tp_price) * 10
                            exit_time = df.index[j]
                            trade_open = False
                            break

                # If trade still open, close at last close
                if trade_open:
                    exit_price = close
                    if is_buy:
                        pnl = (close - entry_price) * 10
                    else:
                        pnl = (entry_price - close) * 10
                    exit_time = df.index[-1]

                trades.append({
                    'symbol': symbol,
                    'signal': signal,
                    'entry': entry_price,
                    'exit': exit_price,
                    'sl': sl_price,
                    'tp': tp_price,
                    'pnl': pnl,
                    'pnl_pips': exit_price - entry_price if is_buy else entry_price - exit_price,
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'status': 'CLOSED' if not trade_open else 'OPEN'
                })

                # Skip to end of trade
                i = j if not trade_open else len(df)

            i += 1

        if not trades:
            return None

        # Calculate stats
        closed = [t for t in trades if t['status'] == 'CLOSED']
        if not closed:
            return None

        wins = [t for t in closed if t['pnl'] > 0]
        losses = [t for t in closed if t['pnl'] < 0]

        total_pnl = sum(t['pnl'] for t in closed)
        win_rate = len(wins) / len(closed) * 100 if closed else 0
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 0
        rrr = avg_win / avg_loss if avg_loss > 0 else 0
        max_loss = min(t['pnl'] for t in closed)
        max_win = max(t['pnl'] for t in closed)

        # Drawdown
        cumsum = np.cumsum([t['pnl'] for t in closed])
        running_max = np.maximum.accumulate(cumsum)
        drawdown = cumsum - running_max
        max_drawdown = min(drawdown) if len(drawdown) > 0 else 0

        # By signal
        by_signal = {}
        for trade in closed:
            sig = trade['signal']
            if sig not in by_signal:
                by_signal[sig] = {'wins': 0, 'losses': 0, 'total_pnl': 0, 'trades': 0}
            by_signal[sig]['trades'] += 1
            by_signal[sig]['total_pnl'] += trade['pnl']
            if trade['pnl'] > 0:
                by_signal[sig]['wins'] += 1
            else:
                by_signal[sig]['losses'] += 1

        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'days': days,
            'total_trades': len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'rrr': rrr,
            'total_pnl': total_pnl,
            'max_win': max_win,
            'max_loss': max_loss,
            'max_drawdown': max_drawdown,
            'by_signal': by_signal,
            'trades': closed
        }

    except Exception as e:
        print(f"Backtest error {symbol} {timeframe}: {e}")
        return None


def backtest_all_symbols(timeframe="5m", days=30):
    """Backtest all 6 symbols."""
    symbols = ["XAU", "BTC", "ETH", "XAG", "USOIL", "DXY"]
    results = {}

    print(f"\nBacktesting {days} days {timeframe} for all symbols...\n")

    for sym in symbols:
        result = backtest_symbol(sym, timeframe, days)
        if result:
            results[sym] = result
            print(f"OK {sym}: {result['total_trades']} trades, WR {result['win_rate']:.1f}%, P&L ${result['total_pnl']:.2f}")
        else:
            print(f"SKIP {sym}: No trades found")

    return results


def format_backtest_report(results):
    """Format backtest results for display."""
    if not results:
        return "No backtest results"

    msg = "BACKTEST REPORT (30 DAYS)\n"
    msg += "=" * 50 + "\n\n"

    total_trades = sum(r['total_trades'] for r in results.values())
    total_pnl = sum(r['total_pnl'] for r in results.values())

    msg += f"Total Trades: {total_trades}\n"
    msg += f"Total P&L: ${total_pnl:.2f}\n\n"

    for sym, result in sorted(results.items()):
        msg += f"[{sym}] ({result['timeframe']})\n"
        msg += f"  Trades: {result['total_trades']} | W: {result['wins']} L: {result['losses']}\n"
        msg += f"  Win Rate: {result['win_rate']:.1f}% | RRR: {result['rrr']:.2f}\n"
        msg += f"  Avg Win: ${result['avg_win']:.2f} | Avg Loss: ${result['avg_loss']:.2f}\n"
        msg += f"  P&L: ${result['total_pnl']:.2f} | Max DD: ${result['max_drawdown']:.2f}\n"

        if result['by_signal']:
            msg += f"  Signals:\n"
            for sig, data in sorted(result['by_signal'].items()):
                wr = data['wins'] / (data['wins'] + data['losses']) * 100 if (data['wins'] + data['losses']) > 0 else 0
                msg += f"    - {sig}: {data['wins']}W-{data['losses']}L ({wr:.0f}%) | ${data['total_pnl']:.2f}\n"
        msg += "\n"

    return msg


if __name__ == "__main__":
    # Backtest M5 all symbols
    results_m5 = backtest_all_symbols("5m", 30)
    print(format_backtest_report(results_m5))

    # Backtest M15 all symbols
    print("\n" + "="*50 + "\n")
    results_m15 = backtest_all_symbols("15m", 30)
    print(format_backtest_report(results_m15))
