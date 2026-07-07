# -*- coding: utf-8 -*-
"""Elliott Wave (heuristic) trên H4 — xác định bias khung lớn cho hệ SMC.

Không phải wave count "chuẩn sách" (Elliott thật cần con người + nhiều fractal),
mà là heuristic đếm chân sóng từ pivot chính để trả lời 2 câu hỏi:
  1. Bias khung to là gì? (UP / DOWN / NEUTRAL)
  2. Đang ở pha nào? (sóng đẩy 1-5 hay điều chỉnh ABC) → cảnh báo sóng 5/sóng C.
"""
from smc_structure import find_swings, analyze_structure


def analyze_elliott(df_h4):
    """Phân tích sóng trên H4.

    Returns dict:
        bias: 'UP' | 'DOWN' | 'NEUTRAL'
        phase: 'IMPULSE' | 'CORRECTION' | 'UNCLEAR'
        wave: số sóng ước tính (1-5 cho impulse, 'A'/'B'/'C' cho correction) hoặc None
        label: text ngắn hiển thị trong alert
        warning: cảnh báo (sóng 5, sóng C sắp xong...) hoặc None
    """
    result = {'bias': 'NEUTRAL', 'phase': 'UNCLEAR', 'wave': None,
              'label': 'H4 chưa rõ sóng (thiếu data)', 'warning': None}

    if df_h4 is None or len(df_h4) < 60:
        return result

    structure = analyze_structure(df_h4, left=3, right=3)
    swings = structure['swings']
    if len(swings) < 5:
        return result

    trend = structure['trend']  # theo BOS/CHoCH events trên H4

    # Pivot chính: đáy thấp nhất (nếu trend UP) / đỉnh cao nhất (nếu DOWN) trong swings
    if trend == 'UP':
        lows = [s for s in swings if s['type'] == 'LOW']
        if not lows:
            return result
        major = min(lows, key=lambda s: s['price'])
    elif trend == 'DOWN':
        highs = [s for s in swings if s['type'] == 'HIGH']
        if not highs:
            return result
        major = max(highs, key=lambda s: s['price'])
    else:
        result['label'] = 'H4 sideway — chưa có sóng chủ đạo'
        return result

    # Các chân sóng (legs) sau pivot chính: đếm số leg THUẬN trend
    after = [s for s in swings if s['i'] >= major['i']]
    if len(after) < 2:
        return result

    legs = []  # mỗi leg: 'UP' hoặc 'DOWN'
    for a, b in zip(after, after[1:]):
        legs.append('UP' if b['price'] > a['price'] else 'DOWN')

    impulse_legs = sum(1 for l in legs if l == trend)

    # Leg cuối cùng đang thuận hay ngược trend?
    last_leg_with_trend = legs[-1] == trend if legs else False

    # Ước tính số sóng: leg thuận thứ k ≈ sóng 2k-1 (1, 3, 5)
    wave_num = min(5, 2 * impulse_legs - 1) if impulse_legs >= 1 else None

    arrow = '↑' if trend == 'UP' else '↓'
    trend_vi = 'tăng' if trend == 'UP' else 'giảm'

    if last_leg_with_trend and wave_num:
        # Đang trong chân sóng đẩy
        result['phase'] = 'IMPULSE'
        result['wave'] = wave_num
        result['bias'] = trend
        result['label'] = f"H4 sóng đẩy ~{wave_num} {trend_vi} {arrow}"
        if wave_num >= 5:
            result['warning'] = f"Sóng 5 {trend_vi} — cuối trend, cẩn thận đảo chiều, ưu tiên chốt sớm"
    else:
        # Leg cuối ngược trend → đang điều chỉnh
        # Đếm leg ngược liên tiếp từ cuối để đoán A/B/C
        counter = 0
        for l in reversed(legs):
            if l != trend:
                counter += 1
            elif counter > 0:
                break
        abc = {1: 'A', 2: 'B', 3: 'C'}.get(min(counter, 3), 'C')
        result['phase'] = 'CORRECTION'
        result['wave'] = abc
        # Điều chỉnh trong trend lớn → bias vẫn theo trend (chờ hết chỉnh để vào tiếp)
        result['bias'] = trend
        result['label'] = f"H4 điều chỉnh sóng {abc} trong trend {trend_vi} {arrow}"
        if abc == 'C':
            result['warning'] = f"Sóng C điều chỉnh — vùng kết thúc chỉnh, canh {('BUY' if trend == 'UP' else 'SELL')} theo trend {trend_vi}"

    return result
