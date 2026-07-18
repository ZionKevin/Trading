# 📖 HƯỚNG DẪN SỬ DỤNG BOT — Zion XAU Signals

> Bot scalp XAU + BTC theo hệ SMC (Smart Money Concepts) + Elliott Wave.
> Cập nhật: 2026-07-18 (Phase 10.2 — bot học từ mọi lệnh đã đóng, tách riêng XAU/BTC)

---

## 1. Bot hoạt động thế nào (đọc 1 lần cho hiểu)

Cứ **5 phút một lần**, bot phân tích từ khung to xuống khung nhỏ:

```
H4  → Sóng Elliott: đang sóng đẩy (1-3-5) hay điều chỉnh (A-B-C)? Bias tăng hay giảm?
H1  → Cấu trúc: BOS (phá thuận trend = tiếp diễn) hay CHoCH (phá ngược = đảo chiều)?
M5/M15 → Giá về Order Block / FVG chưa? Có nến xác nhận (engulfing, pin bar) không?
```

Chỉ khi **các khung thẳng hàng** + giá vào đúng vùng + không mua đắt (premium)
không bán rẻ (discount) → bot mới bắn Alert. **Ít tín hiệu = bình thường.**
Hệ này kén, thà im còn hơn báo bậy.

- Giờ hoạt động: **7h sáng → 5h sáng hôm sau** (giờ VN). Nghỉ 5h-7h sáng (NY vừa đóng, thị trường chết).
- Mỗi lúc chỉ có **1 alert sống** (one-at-a-time). Alert cũ phải đóng thì mới có alert mới.
- **Watchdog** tự dọn: giá chạm SL/TP mà quên báo → bot tự đóng trong ~10 phút.
  Alert treo 4 tiếng không chạm gì → tự huỷ (không tính thắng thua).

---

## 2. Đọc hiểu 1 Alert

```
🔔 Alert #3
🥇 M15 XAU — BUY
Action: Chờ giá test OB M15 4132–4136 và BUY
Entry 4135.2 | SL 4124.8
TP1 4147.0 | TP2 4157.3 | TP3 4169.0
――――――――――
🌊 H4 sóng đẩy ~3 tăng ↑          ← sóng Elliott khung to
📐 H1: BOS ↑ @ 4129 — trend UP    ← cấu trúc vừa phá đỉnh, xu hướng tăng
📦 Zone: OB M15 4132–4136 | Discount (vùng mua rẻ)
🕯️ Nến: Nến nhấn chìm tăng (Bullish Engulfing)
💧 Liquidity target: 4147, 4157, 4169   ← các cụm stop phía trên (mục tiêu giá)
――――――――――
Signal: BUY_SMC_OB_CANDLE 🎯 OB+FVG
Conf: 25% | Session: ASIAN
Report: /tp 3 or /sl 3 or /exit 3 <price>
```

Cách đánh gợi ý: vào 1 phần ở entry, **chốt dần TP1 → TP2**, phần còn lại gồng tới TP3.
SL luôn đặt đúng giá bot đưa (đã clamp 100-150 pip cho XAU).

⚠️ Nếu thấy dòng `⚠️ Sóng 5` hoặc `⚠️ Sóng C` → lệnh cuối trend, đánh nhẹ tay, chốt sớm.

---

## 3. Lệnh Telegram — tra nhanh

### 📊 Xem thị trường
| Lệnh | Làm gì |
|------|--------|
| `/h1` | **Khung to**: sóng Elliott H4 + cấu trúc H1 + liquidity (XAU + BTC) |
| `/m5` | Phân tích SMC khung M5: trend, OB/FVG gần nhất, có setup chưa |
| `/m15` | Như /m5 nhưng khung M15 |
| `/price` | Giá hiện tại 6 symbol + RSI |
| `/trend` | Trend H1 các symbol |
| `/status` | Tổng quan thị trường |
| `/macro` | Lịch kinh tế + sự kiện quan trọng (CPI, NFP, FOMC) |

### ✅ Báo kết quả alert (QUAN TRỌNG — để bot học)
| Lệnh | Làm gì |
|------|--------|
| `/open` | Xem alert nào đang treo |
| `/tp 3` | Alert #3 ăn TP2 (mặc định) |
| `/tp 3 1` | Alert #3 ăn TP1 (số sau là level: 1, 2 hay 3) |
| `/sl 3` | Alert #3 dính SL |
| `/exit 3 4142.5` | Đóng alert #3 ở giá bất kỳ (chốt non/cắt sớm) |

> Quên báo cũng được — watchdog tự xử. Nhưng báo tay thì nhanh và chính xác hơn.

### 🎓 Dạy bot lệnh mày tự đánh
| Lệnh | Làm gì |
|------|--------|
| `/day ...` | Dạy 1 lệnh — **gõ tự do**, xem ví dụ dưới |
| `/trades-taught` | Xem các lệnh đã dạy (kèm ID) |
| `/forget 2` | Xoá lệnh dạy #2 (dạy nhầm/test) |
| `/mystyle` | Bot phân tích style của mày: hay đánh gì, RRR bao nhiêu |

**Ví dụ /day (số thứ tự nào cũng được, nó tự hiểu):**
```
/day buy 4150 sl 4140 tp 4170 test OB H1 + nến engulfing
/day 4150 4140 4170 CHoCH xong quét liquidity        ← 3 số trơn = entry, sl, tp
/day sell btc 63500 sl 63900 tp 62800 FVG premium
/day mua 4150 dừng 4140 chốt 4170                     ← tiếng Việt cũng hiểu
```
Không ghi buy/sell nó tự đoán từ vị trí SL. Gõ nhầm chỗ SL/TP nó tự đảo.

### 📈 Thống kê & học máy
| Lệnh | Làm gì |
|------|--------|
| `/stats` | Thống kê tổng: win rate, P&L, breakdown từng signal |
| `/trades` | 10 trade gần nhất |
| `/learning` | Bot học được gì: signal nào ngon, signal nào rác (tách riêng XAU/BTC, ghi rõ bao nhiêu lệnh thật vs backtest) |
| `/session` | Giờ nào đánh thắng nhiều nhất (tự cập nhật mỗi lần đóng lệnh) |

---

## 4. Quy trình mỗi ngày (gợi ý)

1. Sáng mở Tele gõ `/h1` — xem hôm nay khung to thiên về đâu, sóng mấy.
2. Chờ 🔔 Alert. Đọc phần ngữ cảnh (🌊📐📦🕯️💧) để hiểu TẠI SAO bot kêu vào.
3. Đánh hay bỏ tuỳ mày — nhưng đánh thì nhớ báo `/tp` `/sl` `/exit` để bot học.
4. Lệnh nào mày TỰ đánh ngoài bot mà thấy đẹp → `/day` kể lại cho nó học style.
5. Cuối tuần gõ `/learning` + `/stats` xem hệ đang thắng thua ra sao.

---

## 5. Deploy code mới (khi có ai sửa code hộ)

```bash
# Trên laptop: sau khi sửa code
cd C:\Projects\Trading
git add <files> && git commit -m "..." && git push

# Trên VPS (Web Console: cloud.digitalocean.com → droplet → Web Console)
cd ~/Trading && git stash && git pull && systemctl restart trading-bot
journalctl -u trading-bot -n 25 --no-pager -o cat     # verify
```

⚠️ **TUYỆT ĐỐI KHÔNG** chạy `python telegram_bot_v2.py` trên laptop —
đánh nhau với bot VPS (Telegram 409 Conflict), cả 2 cùng chết.

**Log khởi động chuẩn phải có:**
```
[ALERT] Phase 10 SMC: XAU+BTC | Elliott bias + BOS/CHoCH + OB/FVG + candle confirm
[WATCHDOG] Started — auto TP/SL theo nến, expire sau 4h
```

---

## 6. Bot câm? Checklist tự chẩn

```bash
systemctl status trading-bot                          # còn sống không?
journalctl -u trading-bot -n 50 --no-pager -o cat     # có Traceback đỏ không?
journalctl -u trading-bot --since "6h ago" -o cat | grep -E "SKIP|SCAN|ALERT|WATCHDOG"
```

| Thấy gì | Nghĩa là |
|---------|----------|
| `[SKIP] No good setup...` lặp lại | **Bình thường** — chưa có setup đạt chuẩn, không phải lỗi |
| `1 alert(s) pending, skip posting` | Có alert treo — chờ watchdog xử (tối đa ~4h) hoặc `/open` rồi đóng tay |
| `Conflict` / `409` | Có bot thứ 2 chạy đâu đó (laptop?) — kill nó đi |
| `tvDatafeed ERROR` lặp liên tục | TradingView rớt — bot tự fallback yfinance, giá XAU có thể delay. Bot sẽ tự đăng ⚠️ cảnh báo lên channel (tối đa 1 lần/6h) |
| Không có log gì mới | Service chết — `systemctl restart trading-bot` |
| 5h-7h sáng VN không có gì | **Bình thường** — giờ nghỉ overnight theo thiết kế |

---

## 7. Backtest (kiểm chứng hệ trên data lịch sử)

```bash
# Chạy trên VPS hoặc laptop đều được (KHÔNG đụng bot)
cd ~/Trading && python3 backtest.py 30           # backtest 30 ngày
cd ~/Trading && python3 backtest.py 30 --seed    # backtest + BƠM kết quả vào bot học
```
Dùng chung engine với bot live → kết quả backtest phản ánh đúng cách bot đánh.
Kết quả tham khảo 15 ngày (07/2026): XAU 62% WR +15.9R, BTC 38% WR +4.2R.

**`--seed` là gì?** Bình thường bot cần ~5 lệnh thật mỗi signal mới dám tin (cold-start
chậm cả tháng). `--seed` lấy kết quả backtest làm "kinh nghiệm khởi điểm" — bot có
confidence ngay từ ngày đầu. Lệnh thật sau này cộng dồn thêm, `/learning` luôn ghi rõ
bao nhiêu là lệnh thật, bao nhiêu là backtest. Chạy lại `--seed` sẽ thay seed cũ, không cộng trùng.

---

## 8. File nào chứa gì (cho ai tò mò)

| File | Vai trò |
|------|---------|
| `telegram_bot_v2.py` | Bot chính: 7 task (alert loop, watchdog, learning, report...) |
| `smc_check.py` | ⭐ Engine tín hiệu SMC (não của bot) |
| `smc_structure.py` | BOS/CHoCH, Order Block, FVG, liquidity |
| `elliott_wave.py` | Đếm sóng H4 |
| `candle_patterns.py` | Nến Nhật xác nhận |
| `backtest.py` | Backtest hệ SMC |
| `learning.json` `alert_tracker.json` `trading_profile.json` | Data bot tự ghi (KHÔNG commit vào git) |
| `CLAUDE.md` | Tài liệu kỹ thuật đầy đủ cho AI/dev đọc |
