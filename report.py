# -*- coding: utf-8 -*-
"""Main entry point: generate analysis report (daily hoặc on-demand)."""
import sys
import argparse
from datetime import datetime
from fetch import fetch_symbol, load_all_symbols
from indicators import IndicatorSet
from analyze import Analysis


def analyze_symbol(symbol, timeframe="1d", days=30):
    """Fetch + analyze 1 symbol, return text report."""
    try:
        df = fetch_symbol(symbol, timeframe, days)
        ind = IndicatorSet(df).calculate_all()
        analysis = Analysis(ind, symbol, timeframe)
        return analysis.text_report()
    except Exception as e:
        return f"[ERROR] {symbol} {timeframe}: {e}"


def daily_report_csv(output_file=None):
    """Generate daily report as CSV (structured)."""
    import csv

    symbols = ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]
    timeframe = "1d"
    days = 60

    rows = []
    rows.append({
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
        "symbol": "---",
        "price": "---",
        "trend": "---",
        "trend_strength": "---",
        "momentum": "---",
        "rsi": "---",
        "volatility": "---",
        "pivot": "---",
        "r1": "---",
        "s1": "---"
    })

    for sym in symbols:
        try:
            df = fetch_symbol(sym, timeframe, days)
            ind = IndicatorSet(df).calculate_all()
            analysis = Analysis(ind, sym, timeframe)
            summary = analysis.summary()

            row = {
                "timestamp": summary['timestamp'],
                "symbol": sym,
                "price": f"${summary['close']:,.2f}",
                "trend": summary['trend']['direction'],
                "trend_strength": summary['trend']['strength'],
                "momentum": summary['momentum']['level'],
                "rsi": summary['momentum']['rsi'],
                "volatility": summary['volatility']['level'],
                "pivot": f"${summary['levels']['pivot']:,.2f}",
                "r1": f"${summary['levels']['resistance'][0]:,.2f}",
                "s1": f"${summary['levels']['support'][0]:,.2f}"
            }
            rows.append(row)
        except Exception as e:
            rows.append({
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                "symbol": sym,
                "price": "ERROR",
                "trend": str(e),
                "trend_strength": "---",
                "momentum": "---",
                "rsi": "---",
                "volatility": "---",
                "pivot": "---",
                "r1": "---",
                "s1": "---"
            })

    if output_file:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "symbol", "price", "trend", "trend_strength",
                "momentum", "rsi", "volatility", "pivot", "r1", "s1"
            ])
            writer.writeheader()
            writer.writerows(rows)
        print(f"[OK] Daily CSV report saved: {output_file}")

    return rows


def daily_report(output_file=None):
    """Generate daily report cho 6 symbol (daily timeframe)."""
    symbols = ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]
    timeframe = "1d"
    days = 60

    lines = []
    lines.append("=" * 70)
    lines.append(f"DAILY ANALYSIS REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 70)
    lines.append("")

    for sym in symbols:
        report = analyze_symbol(sym, timeframe, days)
        lines.append(report)
        lines.append("")

    result = "\n".join(lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[OK] Daily report saved to: {output_file}")
    else:
        print(result)

    return result


def on_demand_report(symbol, timeframe="1h"):
    """Generate report on-demand cho 1 symbol."""
    if symbol.upper() not in ["BTC", "ETH", "XAU", "XAG", "USOIL", "DXY"]:
        print(f"[ERROR] Unknown symbol: {symbol}")
        return

    # Infer days based on timeframe
    if timeframe in ["1m", "5m", "15m", "30m"]:
        days = 7
    elif timeframe in ["1h", "4h"]:
        days = 30
    else:
        days = 90

    report = analyze_symbol(symbol.upper(), timeframe, days)
    print(report)


def main():
    parser = argparse.ArgumentParser(
        description="Trading analysis report generator"
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="Symbol: BTC/ETH/XAU/XAG/USOIL/DXY. Omit for daily report."
    )
    parser.add_argument(
        "-t", "--timeframe",
        default="1h",
        help="Timeframe: 1m/5m/15m/30m/1h/4h/1d (default: 1h)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save report to file (text or CSV)"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export daily report as CSV (daily mode only)"
    )

    args = parser.parse_args()

    if args.symbol:
        # On-demand mode
        print(f"Fetching {args.symbol} {args.timeframe}...")
        on_demand_report(args.symbol, args.timeframe)
    else:
        # Daily mode
        print(f"Generating daily report for all 6 symbols...")
        if args.csv:
            daily_report_csv(args.output)
        else:
            daily_report(args.output)


if __name__ == "__main__":
    main()
