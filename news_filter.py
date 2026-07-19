# -*- coding: utf-8 -*-
"""News filter — lịch kinh tế THẬT từ ForexFactory (feed công khai, không cần API key).

Nhiệm vụ:
1. check_news_blackout(): đang trong ±30' quanh tin đỏ USD (NFP/CPI/FOMC...) không?
   → smart_alert_loop tạm dừng bắn alert (SL 100-150 pip bay trong 1 nến tin).
2. format_upcoming_news(): lịch tin đỏ tuần này cho lệnh /news (giờ VN).

Fail-open: mạng lỗi / feed sập → KHÔNG chặn alert (bot chạy như cũ), chỉ log.
Cache: memory + đĩa (news_cache.json, đã gitignore), refresh mỗi 6h.
"""
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Feed lịch tuần của ForexFactory (nfs.faireconomy.media) — chuẩn dân forex xài nhiều năm
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_FILE = "news_cache.json"
CACHE_TTL = 6 * 3600            # refresh feed mỗi 6h
DISK_CACHE_MAX_AGE = 48 * 3600  # cache đĩa quá 48h coi như hết hạn
BLACKOUT_BEFORE_MIN = 30        # khoá alert 30' TRƯỚC tin
BLACKOUT_AFTER_MIN = 30         # và 30' SAU tin

VN_TZ = timezone(timedelta(hours=7))

_state = {'events': None, 'fetched_at': 0.0}


def _fetch_events():
    """Lấy raw events, ưu tiên memory cache → mạng → cache đĩa. Trả None nếu bó tay."""
    now = time.time()
    if _state['events'] is not None and now - _state['fetched_at'] < CACHE_TTL:
        return _state['events']

    try:
        r = requests.get(FF_URL, timeout=10,
                         headers={'User-Agent': 'Mozilla/5.0 (trading-bot)'})
        r.raise_for_status()
        events = r.json()
        _state['events'] = events
        _state['fetched_at'] = now
        try:
            Path(CACHE_FILE).write_text(
                json.dumps({'fetched_at': now, 'events': events}), encoding='utf-8')
        except OSError:
            pass
        return events
    except Exception as e:
        logger.warning(f"news_filter: fetch fail ({e}) — thử cache đĩa")

    # Mạng lỗi → cache đĩa nếu còn tươi
    try:
        cached = json.loads(Path(CACHE_FILE).read_text(encoding='utf-8'))
        if now - cached.get('fetched_at', 0) < DISK_CACHE_MAX_AGE:
            _state['events'] = cached['events']
            _state['fetched_at'] = cached['fetched_at']
            return cached['events']
    except Exception:
        pass
    return _state['events']  # có gì xài nấy (kể cả None)


def _high_usd_events():
    """Lọc tin ĐỎ (impact High) của USD, parse giờ về UTC aware.

    Returns: list {'title', 'time' (datetime UTC)} sort theo giờ.
    """
    out = []
    for e in _fetch_events() or []:
        if e.get('impact') != 'High' or e.get('country') != 'USD':
            continue
        try:
            ts = datetime.fromisoformat(e['date'])  # dạng "2026-07-18T08:30:00-04:00"
        except (KeyError, ValueError, TypeError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out.append({'title': e.get('title', '?'), 'time': ts.astimezone(timezone.utc)})
    out.sort(key=lambda x: x['time'])
    return out


def check_news_blackout():
    """(True, event) nếu đang trong cửa sổ ±30' quanh 1 tin đỏ USD, ngược lại (False, None).

    Fail-open: không lấy được lịch → (False, None), bot chạy bình thường.
    """
    now = datetime.now(timezone.utc)
    for ev in _high_usd_events():
        delta_min = (ev['time'] - now).total_seconds() / 60
        # delta > 0: tin sắp ra; delta < 0: tin đã ra
        if -BLACKOUT_AFTER_MIN <= delta_min <= BLACKOUT_BEFORE_MIN:
            return True, ev
    return False, None


def format_upcoming_news():
    """Lịch tin đỏ USD tuần này (giờ VN) — cho lệnh /news."""
    events = _high_usd_events()
    if not events:
        return ("Không lấy được lịch tin (feed lỗi hoặc tuần này không có tin đỏ USD).\n"
                "Bot vẫn chạy bình thường — chỉ là không có news filter.")

    now = datetime.now(timezone.utc)
    lines = ["📅 TIN ĐỎ USD TUẦN NÀY (giờ VN)", "=" * 34]
    for ev in events:
        vn = ev['time'].astimezone(VN_TZ)
        if ev['time'] < now - timedelta(minutes=BLACKOUT_AFTER_MIN):
            mark = "✔️"   # đã ra
        elif abs((ev['time'] - now).total_seconds()) / 60 <= max(BLACKOUT_BEFORE_MIN, BLACKOUT_AFTER_MIN):
            mark = "🔴"   # đang trong cửa sổ blackout
        else:
            mark = "⏳"   # sắp tới
        lines.append(f"{mark} {vn:%a %d/%m %H:%M} — {ev['title']}")
    lines.append("")
    lines.append(f"⏸️ Bot tự dừng alert {BLACKOUT_BEFORE_MIN}' trước → {BLACKOUT_AFTER_MIN}' sau mỗi tin đỏ.")
    lines.append("Lý do: nến tin spike 1 giây là bay SL, không setup SMC nào sống nổi.")
    return "\n".join(lines)


if __name__ == "__main__":
    blackout, ev = check_news_blackout()
    print(f"Blackout: {blackout}" + (f" ({ev['title']})" if ev else ""))
    print()
    print(format_upcoming_news())
