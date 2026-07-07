# -*- coding: utf-8 -*-
"""Backtest hệ SMC (Phase 10) trên data lịch sử — walk-forward bar-by-bar.

Dùng CHUNG engine analyze_smc_core với live bot → backtest gì, live chạy nấy.
Chạy: python backtest.py [days]     (default 25 ngày, khung entry M15)
"""
import sys
from fetch import fetch_symbol
from smc_check import analyze_smc_core
from trade_tracker import get_risk_per_pip

SYMBOLS = ["XAU", "BTC"]
ENTRY_TF = "15m"
# Cửa sổ data mỗi lần phân tích — khớp lượng data live bot fetch
LTF_WINDOW = 400
H1_WINDOW = 350
H4_WINDOW = 250
WARMUP = 300          # bỏ N nến đầu (chưa đủ data phân tích)
MAX_HOLD_BARS = 96    # 24h trên M15 — quá thì đóng tại close


def _naive(df):
    """Bỏ timezone để so sánh index giữa các khung."""
    if getattr(df.index, 'tz', None) is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df


def _close_trade(tr, exit_price, result, exit_time, trades, symbol):
    side = 1 if tr['dir'] == 'BUY' else -1
    risk = abs(tr['entry'] - tr['sl'])
    pnl_usd = (exit_price - tr['entry']) * get_risk_per_pip(symbol) * side
    pnl_r = ((exit_price - tr['entry']) * side / risk) if risk > 0 else 0
    trades.append({**tr, 'exit': exit_price, 'result': result,
                   'exit_time': exit_time, 'pnl_usd': pnl_usd, 'pnl_r': pnl_r})


def backtest_symbol(symbol, days=25):
    """Walk-forward backtest 1 symbol. Returns list trades."""
    print(f"  Fetching {symbol} data...")
    df_ltf = _naive(fetch_symbol(symbol, ENTRY_TF, days))
    df_h1 = _naive(fetch_symbol(symbol, "1h", days))
    df_h4 = _naive(fetch_symbol(symbol, "4h", 60))

    n = len(df_ltf)
    print(f"  {symbol}: {n} nến {ENTRY_TF}, {len(df_h1)} nến H1, {len(df_h4)} nến H4 — simulating...")

    trades = []
    tr = None  # trade đang mở (one-at-a-time như live)

    for i in range(WARMUP, n):
        t = df_ltf.index[i]
        hi = float(df_ltf['High'].iloc[i])
        lo = float(df_ltf['Low'].iloc[i])
        cl = float(df_ltf['Close'].iloc[i])

        # ===== 1. Quản lý trade đang mở =====
        if tr is not None:
            is_buy = tr['dir'] == 'BUY'
            sl_hit = (lo <= tr['sl']) if is_buy else (hi >= tr['sl'])
            if sl_hit:
                # Nến chạm cả SL lẫn TP → conservative tính SL,
                # trừ khi TP đã chạm ở nến TRƯỚC (best_tp > 0)
                if tr['best_tp'] > 0:
                    lvl = tr['best_tp']
                    _close_trade(tr, tr[f'tp{lvl}'], f'TP{lvl}', t, trades, symbol)
                else:
                    _close_trade(tr, tr['sl'], 'SL', t, trades, symbol)
                tr = None
                continue

            if is_buy:
                if hi >= tr['tp3']:
                    tr['best_tp'] = 3
                elif hi >= tr['tp2']:
                    tr['best_tp'] = max(tr['best_tp'], 2)
                elif hi >= tr['tp1']:
                    tr['best_tp'] = max(tr['best_tp'], 1)
            else:
                if lo <= tr['tp3']:
                    tr['best_tp'] = 3
                elif lo <= tr['tp2']:
                    tr['best_tp'] = max(tr['best_tp'], 2)
                elif lo <= tr['tp1']:
                    tr['best_tp'] = max(tr['best_tp'], 1)

            if tr['best_tp'] == 3:
                _close_trade(tr, tr['tp3'], 'TP3', t, trades, symbol)
                tr = None
            elif i - tr['i'] >= MAX_HOLD_BARS:
                if tr['best_tp'] > 0:
                    lvl = tr['best_tp']
                    _close_trade(tr, tr[f'tp{lvl}'], f'TP{lvl}', t, trades, symbol)
                else:
                    _close_trade(tr, cl, 'EXIT', t, trades, symbol)
                tr = None
            continue

        # ===== 2. Tìm setup mới (đúng engine live) =====
        ltf_slice = df_ltf.iloc[max(0, i - LTF_WINDOW):i + 1]
        h1_slice = df_h1[df_h1.index <= t].tail(H1_WINDOW)
        h4_slice = df_h4[df_h4.index <= t].tail(H4_WINDOW)
        if len(h1_slice) < 50 or len(h4_slice) < 60:
            continue

        setup = analyze_smc_core(symbol, ENTRY_TF, h4_slice, h1_slice, ltf_slice)
        if setup and setup['volume_is_strong']:
            tr = {
                'dir': 'BUY' if setup['direction'] == 'UP' else 'SELL',
                'signal': setup['signal'],
                'entry': setup['entry'], 'sl': setup['sl'],
                'tp1': setup['tp1'], 'tp2': setup['tp'], 'tp3': setup['tp3'],
                'i': i, 'time': t, 'best_tp': 0,
            }

    # Trade còn mở cuối kỳ → bỏ (không đủ dữ liệu kết luận)
    return trades


def format_report(symbol, trades):
    if not trades:
        return f"\n=== {symbol}: 0 trades trong kỳ backtest ===\n(SMC kén setup — bình thường nếu ít trade)"

    wins = [t for t in trades if t['result'].startswith('TP')]
    losses = [t for t in trades if t['result'] == 'SL']
    exits = [t for t in trades if t['result'] == 'EXIT']
    decided = len(wins) + len(losses)
    wr = len(wins) / decided * 100 if decided else 0
    total_r = sum(t['pnl_r'] for t in trades)
    total_usd = sum(t['pnl_usd'] for t in trades)

    lines = [f"\n=== {symbol} — {len(trades)} trades ==="]
    lines.append(f"Win rate: {wr:.0f}% ({len(wins)}W-{len(losses)}L, {len(exits)} timeout)")
    lines.append(f"Tổng: {total_r:+.1f}R | ${total_usd:+,.0f} (theo công thức P&L bot)")

    # TP level hit rates
    for lvl in (1, 2, 3):
        hits = sum(1 for t in trades if t['result'] == f'TP{lvl}')
        if hits:
            lines.append(f"  TP{lvl} exit: {hits} lần")

    # Per-signal breakdown
    lines.append("Per signal:")
    sigs = {}
    for t in trades:
        sigs.setdefault(t['signal'], []).append(t)
    for sig, ts in sorted(sigs.items(), key=lambda x: -len(x[1])):
        w = sum(1 for t in ts if t['result'].startswith('TP'))
        l = sum(1 for t in ts if t['result'] == 'SL')
        r = sum(t['pnl_r'] for t in ts)
        d = w + l
        swr = w / d * 100 if d else 0
        lines.append(f"  {sig}: {len(ts)} trades, {swr:.0f}% WR, {r:+.1f}R")

    # Trade list (10 gần nhất)
    lines.append("10 trades gần nhất:")
    for t in trades[-10:]:
        lines.append(f"  {str(t['time'])[:16]} {t['dir']} {t['entry']:.1f} → {t['exit']:.1f} "
                     f"[{t['result']}] {t['pnl_r']:+.1f}R ({t['signal']})")

    return "\n".join(lines)


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    print(f"SMC BACKTEST — {days} ngày, khung entry {ENTRY_TF}, symbols: {SYMBOLS}")
    print("(Walk-forward bar-by-bar, one-trade-at-a-time, cùng engine với live bot)")

    all_trades = []
    for sym in SYMBOLS:
        try:
            trades = backtest_symbol(sym, days)
            print(format_report(sym, trades))
            all_trades.extend(trades)
        except Exception as e:
            print(f"\n=== {sym}: ERROR {e} ===")

    if all_trades:
        total_r = sum(t['pnl_r'] for t in all_trades)
        wins = sum(1 for t in all_trades if t['result'].startswith('TP'))
        losses = sum(1 for t in all_trades if t['result'] == 'SL')
        d = wins + losses
        print(f"\n{'=' * 40}")
        print(f"TỔNG: {len(all_trades)} trades | WR {wins / d * 100 if d else 0:.0f}% | {total_r:+.1f}R")
        print("Lưu ý: chưa tính slippage/spread. Kết quả quá khứ không đảm bảo tương lai.")


if __name__ == "__main__":
    main()
