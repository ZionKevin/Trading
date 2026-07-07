# -*- coding: utf-8 -*-
"""SMC signal engine — thay thế hệ Fibo/MA89/Pivot cũ.

Phân tích top-down:
    H4  → Elliott bias (sóng đẩy/điều chỉnh, hướng khung to)
    H1  → cấu trúc BOS/CHoCH → hướng đánh + liquidity targets
    M5/M15 → entry tại Order Block / FVG chưa mitigated + nến Nhật xác nhận

Kỷ luật SMC: BUY chỉ ở vùng DISCOUNT/EQ của dealing range H1, SELL chỉ ở PREMIUM/EQ.
"""
import logging
from datetime import datetime

from fetch import fetch_symbol
from smc_structure import (
    analyze_structure, find_order_blocks, find_fvg,
    find_liquidity_pools, premium_discount, calc_atr,
)
from candle_patterns import detect_confirmation
from elliott_wave import analyze_elliott
from scalp_check import check_volume_strength

logger = logging.getLogger(__name__)

# SL clamp per-symbol (USD) — giữ nguyên preference của user (XAU 100-150 pip)
SL_RANGE_USD = {
    'XAU': (10, 15),
    'BTC': (200, 500),
    'ETH': (30, 70),
    'XAG': (0.2, 0.5),
    'USOIL': (0.5, 1.0),
    'DXY': (0.3, 0.7),
}

# 8 signal types của hệ SMC
SMC_SIGNALS = [
    'BUY_SMC_OB', 'BUY_SMC_OB_CANDLE', 'BUY_SMC_FVG', 'BUY_SMC_FVG_CANDLE',
    'SELL_SMC_OB', 'SELL_SMC_OB_CANDLE', 'SELL_SMC_FVG', 'SELL_SMC_FVG_CANDLE',
]


def _fetch_context(symbol, tf):
    """Fetch 3 khung: H4 (Elliott), H1 (structure), LTF (entry).

    Guard chống LỆCH NGUỒN: nếu 1 khung rớt TradingView và fallback sang yfinance
    (XAU → GC=F futures lệch ~$20 so với spot), phân tích trộn 2 nguồn sẽ ra
    structure/TP sai → raise để bỏ vòng quét này thay vì phân tích bậy.
    """
    df_h4 = fetch_symbol(symbol, "4h", 60)
    df_h1 = fetch_symbol(symbol, "1h", 14)
    df_ltf = fetch_symbol(symbol, tf, 7)

    # Nến đang chạy của cả 3 khung = cùng giá hiện tại → close cuối phải sát nhau
    closes = [float(df_h4['Close'].iloc[-1]), float(df_h1['Close'].iloc[-1]),
              float(df_ltf['Close'].iloc[-1])]
    ref = closes[2]  # LTF là chuẩn
    if ref > 0 and max(abs(c - ref) / ref for c in closes) > 0.002:  # 0.2%
        raise ValueError(
            f"{symbol}: data 3 khung lệch nhau {closes} — nghi trộn nguồn TV/yfinance, bỏ vòng này")

    return df_h4, df_h1, df_ltf


def _zone_tap(df_ltf, zone, direction):
    """Giá hiện tại có đang test zone không (chạm nhưng chưa thủng)?"""
    low = float(df_ltf['Low'].iloc[-1])
    high = float(df_ltf['High'].iloc[-1])
    close = float(df_ltf['Close'].iloc[-1])
    if direction == 'UP':
        return low <= zone['top'] and close >= zone['bottom']
    else:
        return high >= zone['bottom'] and close <= zone['top']


def _pick_tp(entry, risk, pools, direction, mults=(1.0, 2.0, 3.0)):
    """Chọn 3 TP: ưu tiên liquidity pool thật, fallback theo bội số risk."""
    tps = []
    used = set()
    for mult in mults:
        target_min = entry + mult * risk * 0.8 if direction == 'UP' else entry - mult * risk * 0.8
        pick = None
        for p in pools:
            if p in used:
                continue
            if direction == 'UP' and p >= target_min:
                pick = p
                break
            if direction == 'DOWN' and p <= target_min:
                pick = p
                break
        if pick is None:
            pick = entry + mult * risk if direction == 'UP' else entry - mult * risk
        else:
            used.add(pick)
        tps.append(pick)
    # Đảm bảo thứ tự TP1 < TP2 < TP3 (BUY) / ngược lại (SELL)
    tps = sorted(tps) if direction == 'UP' else sorted(tps, reverse=True)
    return tps


def analyze_symbol_smc(symbol, tf="15m"):
    """Tìm setup SMC cho 1 symbol + timeframe (fetch data live rồi gọi core)."""
    try:
        df_h4, df_h1, df_ltf = _fetch_context(symbol, tf)
    except Exception as e:
        logger.error(f"analyze_symbol_smc fetch {symbol} {tf}: {e}")
        return None
    return analyze_smc_core(symbol, tf, df_h4, df_h1, df_ltf)


def analyze_smc_core(symbol, tf, df_h4, df_h1, df_ltf):
    """Engine SMC thuần (không fetch) — dùng chung cho live bot VÀ backtest.

    Returns:
        dict setup (tương thích smart_alert_loop) hoặc None.
        Kèm 'context' đầy đủ để alert giải thích bot đang nghĩ gì.
    """
    if len(df_ltf) < 50 or len(df_h1) < 50:
        return None

    # ===== Khung to =====
    elliott = analyze_elliott(df_h4)
    h1 = analyze_structure(df_h1, left=3, right=3)

    h1_trend = h1['trend']
    if h1_trend not in ('UP', 'DOWN'):
        return None  # H1 sideway — không đánh

    # Elliott bias ngược H1 → bỏ (khung to không ủng hộ)
    if elliott['bias'] != 'NEUTRAL' and elliott['bias'] != h1_trend:
        return None

    direction = h1_trend
    is_buy = direction == 'UP'
    price = float(df_ltf['Close'].iloc[-1])

    # ===== Kỷ luật premium/discount (dealing range H1) =====
    pd_zone = premium_discount(price, h1['range_high'], h1['range_low'])
    if is_buy and pd_zone == 'PREMIUM':
        return None   # không BUY vùng đắt
    if not is_buy and pd_zone == 'DISCOUNT':
        return None   # không SELL vùng rẻ

    # ===== Entry zone trên LTF =====
    ltf = analyze_structure(df_ltf, left=3, right=3)
    obs = find_order_blocks(df_ltf, ltf['events'], direction=direction)
    fvgs = find_fvg(df_ltf, direction=direction)

    zone = None
    zone_type = None
    for ob in obs:
        if _zone_tap(df_ltf, ob, direction):
            zone, zone_type = ob, 'OB'
            break
    if zone is None:
        for gap in fvgs:
            if _zone_tap(df_ltf, gap, direction):
                zone, zone_type = gap, 'FVG'
                break
    if zone is None:
        return None  # giá chưa về vùng entry nào

    # Confluence: OB và FVG chồng lên nhau = zone kép
    has_confluence = False
    if zone_type == 'OB':
        for gap in fvgs:
            if gap['bottom'] <= zone['top'] and gap['top'] >= zone['bottom']:
                has_confluence = True
                break

    # ===== Nến Nhật xác nhận =====
    candle = detect_confirmation(df_ltf, direction=direction)

    # ===== Signal name =====
    side = 'BUY' if is_buy else 'SELL'
    base = f"{side}_SMC_{zone_type}"
    signal = base + ('_CANDLE' if candle else '')

    # ===== SL/TP =====
    atr_ltf = calc_atr(df_ltf)
    atr_h1 = h1['atr']
    entry = price
    sl_min, sl_max = SL_RANGE_USD.get(symbol, (1.0 * atr_ltf, 2.5 * atr_ltf))

    if is_buy:
        raw_dist = entry - (zone['bottom'] - 0.5 * atr_ltf)   # dưới đáy zone + buffer
        sl_dist = max(sl_min, min(raw_dist, sl_max))
        sl = entry - sl_dist
        pools = find_liquidity_pools(h1, entry, atr_h1, side='ABOVE')
    else:
        raw_dist = (zone['top'] + 0.5 * atr_ltf) - entry
        sl_dist = max(sl_min, min(raw_dist, sl_max))
        sl = entry + sl_dist
        pools = find_liquidity_pools(h1, entry, atr_h1, side='BELOW')

    tp1, tp2, tp3 = _pick_tp(entry, sl_dist, pools, direction)

    # ===== Volume (BTC có volume thật, XAU auto-pass) =====
    vol = check_volume_strength(df_ltf, lookback=20, symbol=symbol)

    # ===== Context cho alert =====
    ev = h1['last_event']
    ev_text = "chưa có event"
    if ev:
        ev_name = ev['event'].replace('_UP', ' ↑').replace('_DOWN', ' ↓').replace('CHOCH', 'CHoCH')
        ev_text = f"{ev_name} @ {ev['price']:.0f}"

    pd_text = {'DISCOUNT': 'Discount (vùng mua rẻ)', 'PREMIUM': 'Premium (vùng bán đắt)',
               'EQUILIBRIUM': 'Equilibrium (giữa range)', 'UNKNOWN': 'n/a'}[pd_zone]

    context = {
        'elliott_label': elliott['label'],
        'elliott_warning': elliott['warning'],
        'h1_trend': h1_trend,
        'h1_event': ev_text,
        'zone_type': zone_type,
        'zone_text': f"{zone_type} {tf.upper()} {zone['bottom']:.0f}–{zone['top']:.0f}",
        'candle': candle['name_vi'] if candle else None,
        'candle_strength': candle['strength'] if candle else 0,
        'pd_text': pd_text,
        'has_confluence': has_confluence,
        'liquidity_pools': pools[:3],
    }

    return {
        'entry': entry,
        'sl': sl,
        'tp': tp2,      # TP2 = primary (tương thích trade_tracker)
        'tp1': tp1,
        'tp3': tp3,
        'signal': signal,
        'direction': direction,
        'volume_is_strong': vol['is_strong'],
        'volume_ratio': vol['ratio'],
        'atr': atr_ltf,
        'context': context,
        'fibo_info': None,  # tương thích code cũ
    }


# ============================================================
# Format cho Telegram commands
# ============================================================

SMC_SYMBOLS = ["XAU", "BTC"]
_EMOJI = {"XAU": "🥇", "BTC": "🔵"}


def format_smc_analysis(tf="5m"):
    """Cho /m5 /m15: phân tích SMC đầy đủ XAU + BTC (kể cả khi chưa có setup)."""
    lines = [f"SMC {tf.upper()} — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in SMC_SYMBOLS:
        emoji = _EMOJI.get(sym, '')
        try:
            df_h4, df_h1, df_ltf = _fetch_context(sym, tf)
            elliott = analyze_elliott(df_h4)
            h1 = analyze_structure(df_h1)
            price = float(df_ltf['Close'].iloc[-1])
            pd_zone = premium_discount(price, h1['range_high'], h1['range_low'])

            ev = h1['last_event']
            ev_text = "chưa có"
            if ev:
                ev_text = ev['event'].replace('_UP', ' ↑').replace('_DOWN', ' ↓').replace('CHOCH', 'CHoCH') + f" @ {ev['price']:.0f}"

            lines.append(f"{emoji} {sym} — {price:.1f}")
            lines.append(f"  {elliott['label']}")
            lines.append(f"  H1: trend {h1['trend']} | {ev_text} | {pd_zone}")

            # Zones LTF theo hướng H1
            if h1['trend'] in ('UP', 'DOWN'):
                ltf = analyze_structure(df_ltf)
                obs = find_order_blocks(df_ltf, ltf['events'], direction=h1['trend'])
                fvgs = find_fvg(df_ltf, direction=h1['trend'])
                if obs:
                    ob = obs[0]
                    lines.append(f"  OB gần nhất: {ob['bottom']:.0f}–{ob['top']:.0f}" + (" (đã tap)" if ob['tapped'] else " (chưa tap)"))
                if fvgs:
                    g = fvgs[0]
                    lines.append(f"  FVG gần nhất: {g['bottom']:.0f}–{g['top']:.0f}")
                if not obs and not fvgs:
                    lines.append("  Chưa có OB/FVG hợp lệ")

            setup = analyze_symbol_smc(sym, tf)
            if setup:
                d = "BUY" if setup['direction'] == 'UP' else "SELL"
                lines.append(f"  ➜ SETUP {d}: entry {setup['entry']:.1f} | SL {setup['sl']:.1f} | TP2 {setup['tp']:.1f}")
                lines.append(f"    Signal: {setup['signal']}")
            else:
                lines.append("  Chưa đủ điều kiện setup")
        except Exception as e:
            lines.append(f"{emoji} {sym}: ERROR {str(e)[:60]}")
        lines.append("")

    return "\n".join(lines)


def format_smc_htf():
    """Cho /h1: bias khung to — H4 Elliott + cấu trúc H1 (XAU + BTC)."""
    lines = [f"KHUNG TO (H4 Elliott + H1 Structure) — {datetime.now().strftime('%H:%M UTC')}\n"]

    for sym in SMC_SYMBOLS:
        emoji = _EMOJI.get(sym, '')
        try:
            df_h4 = fetch_symbol(sym, "4h", 60)
            df_h1 = fetch_symbol(sym, "1h", 14)
            elliott = analyze_elliott(df_h4)
            h1 = analyze_structure(df_h1)
            price = float(df_h1['Close'].iloc[-1])

            ev = h1['last_event']
            ev_text = "chưa có"
            if ev:
                ev_text = ev['event'].replace('_UP', ' ↑').replace('_DOWN', ' ↓').replace('CHOCH', 'CHoCH') + f" @ {ev['price']:.0f}"

            pools_up = find_liquidity_pools(h1, price, h1['atr'], side='ABOVE')
            pools_dn = find_liquidity_pools(h1, price, h1['atr'], side='BELOW')

            lines.append(f"{emoji} {sym} — {price:.1f}")
            lines.append(f"  {elliott['label']}")
            if elliott['warning']:
                lines.append(f"  ⚠️ {elliott['warning']}")
            lines.append(f"  H1 trend: {h1['trend']} | Event: {ev_text}")
            if pools_up:
                lines.append(f"  Liquidity trên: {', '.join(f'{p:.0f}' for p in pools_up[:3])}")
            if pools_dn:
                lines.append(f"  Liquidity dưới: {', '.join(f'{p:.0f}' for p in pools_dn[:3])}")
        except Exception as e:
            lines.append(f"{emoji} {sym}: ERROR {str(e)[:60]}")
        lines.append("")

    return "\n".join(lines)
