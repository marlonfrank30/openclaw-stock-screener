#!/usr/bin/env python3
"""
analyze_stock.py — Single or multi-stock deep analysis for OpenClaw.
Uses Alpha Vantage API (works from server/datacenter IPs, unlike Yahoo Finance).

Setup:
  export ALPHA_VANTAGE_KEY="your_key_here"
  # Get a free key at: https://www.alphavantage.co/support/#api-key

Usage:
  python3 analyze_stock.py --ticker NVDA
  python3 analyze_stock.py --ticker NVDA --period full
  python3 analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare
  python3 analyze_stock.py --ticker NVDA --output json
"""

import argparse
import json
import sys
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from av_client import get_api_key, fetch_quote, fetch_daily, fetch_overview
from indicators import rsi, macd, bollinger_bands, sma, volume_spike, signal_summary


# ---------------------------------------------------------------------------
# Fetch & assemble
# ---------------------------------------------------------------------------

def fetch_stock(ticker: str, period: str = "compact", api_key: str = None) -> dict:
    key = get_api_key(api_key)
    ticker = ticker.upper()

    # 1. Current quote
    quote = fetch_quote(ticker, key)
    if not quote:
        return {"error": f"No quote data found for {ticker}. Check the ticker symbol."}

    # 2. Price history for technical indicators
    time.sleep(0.5)  # respect rate limit
    hist = fetch_daily(ticker, key, outputsize=period)
    if hist.empty:
        return {"error": f"No price history found for {ticker}."}

    # 3. Fundamentals
    time.sleep(0.5)
    overview = fetch_overview(ticker, key)

    close  = hist["close"]
    vol    = hist["volume"]

    # Technical indicators
    r    = rsi(close)
    m    = macd(close)
    bb   = bollinger_bands(close)
    s20  = sma(close, 20)
    s50  = sma(close, 50)
    s200 = sma(close, 200)
    vs   = volume_spike(vol)
    sigs = signal_summary(close, vol)

    price     = quote["price"] or close.iloc[-1]
    high_52w  = overview.get("52w_high") or close.max()
    low_52w   = overview.get("52w_low")  or close.min()
    pct_high  = ((price - high_52w) / high_52w * 100) if high_52w else None

    def _r(v, d=2):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return round(float(v), d)

    return {
        "ticker":   ticker,
        "name":     overview.get("name", ticker),
        "sector":   overview.get("sector", "N/A"),
        "industry": overview.get("industry", "N/A"),
        "price":    price,
        "currency": overview.get("currency", "USD"),
        "change":       quote.get("change"),
        "change_pct":   quote.get("change_pct"),
        "52w_high":     high_52w,
        "52w_low":      low_52w,
        "pct_from_52w_high": _r(pct_high, 1),
        "market_cap":   overview.get("market_cap"),
        "beta":         overview.get("beta"),
        "analyst_target": overview.get("analyst_target"),

        "technical": {
            "rsi_14":           _r(r.iloc[-1], 1),
            "macd_line":        _r(m["macd"].iloc[-1], 4),
            "macd_signal":      _r(m["signal"].iloc[-1], 4),
            "macd_histogram":   _r(m["histogram"].iloc[-1], 4),
            "sma_20":           _r(s20.iloc[-1]),
            "sma_50":           overview.get("50d_ma") or _r(s50.iloc[-1]),
            "sma_200":          overview.get("200d_ma") or _r(s200.iloc[-1]),
            "bb_upper":         _r(bb["upper"].iloc[-1]),
            "bb_lower":         _r(bb["lower"].iloc[-1]),
            "volume_spike_ratio": _r(vs.iloc[-1]),
        },

        "valuation": {
            "pe_ratio":   overview.get("pe_ratio"),
            "forward_pe": overview.get("forward_pe"),
            "ps_ratio":   overview.get("ps_ratio"),
            "pb_ratio":   overview.get("pb_ratio"),
            "peg_ratio":  overview.get("peg_ratio"),
            "ev_ebitda":  overview.get("ev_ebitda"),
        },

        "profitability": {
            "net_margin":       overview.get("profit_margin"),
            "operating_margin": overview.get("operating_margin"),
            "roe":              overview.get("roe"),
            "roa":              overview.get("roa"),
        },

        "growth": {
            "revenue_growth": overview.get("revenue_growth"),
            "eps_growth":     overview.get("eps_growth"),
        },

        "financial_health": {
            "debt_equity":   overview.get("debt_equity"),
            "current_ratio": overview.get("current_ratio"),
        },

        "dividends": {
            "yield":        overview.get("dividend_yield"),
            "payout_ratio": overview.get("payout_ratio"),
        },

        "signal":    sigs,
        "data_date": str(hist.index[-1].date()),
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fv(v, d=2):
    return "N/A" if v is None else f"{v:,.{d}f}"

def _fp(v):
    if v is None: return "N/A"
    # Alpha Vantage returns margins as decimals (0.55) or whole numbers (55) — normalise
    pct = v if abs(v) > 1 else v * 100
    return f"{pct:.1f}%"

def _fc(v):
    if v is None: return "N/A"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def _rsi_lbl(v):
    if v is None: return "N/A"
    if v < 30:    return "Oversold 🟢"
    if v > 70:    return "Overbought 🔴"
    return "Neutral"

def _val_ctx(metric, v):
    if v is None: return ""
    ranges = {
        "pe":  [(0,10,"Potentially undervalued"),(10,20,"Fairly valued"),(20,30,"Growth premium"),(30,9999,"High / speculative")],
        "ps":  [(0,1,"Very cheap"),(1,3,"Reasonable"),(3,8,"Growth premium"),(8,9999,"Expensive")],
        "pb":  [(0,1,"Below book"),(1,3,"Reasonable"),(3,8,"Premium"),(8,9999,"High premium")],
        "peg": [(0,1,"Undervalued vs growth"),(1,2,"Fair"),(2,9999,"Overvalued vs growth")],
    }
    for lo, hi, label in ranges.get(metric, []):
        if lo <= v < hi: return label
    return ""

def format_report(data: dict) -> str:
    if "error" in data:
        return f"## ❌ Error\n\n{data['error']}"

    t  = data["technical"]
    va = data["valuation"]
    pr = data["profitability"]
    gr = data["growth"]
    fh = data["financial_health"]
    dv = data["dividends"]
    s  = data["signal"]
    icon = {"BULLISH":"🟢","BEARISH":"🔴","NEUTRAL":"🟡"}.get(s["verdict"],"⚪")

    chg_pct = data.get("change_pct")
    chg_str = f"{float(chg_pct):+.2f}%" if chg_pct else "N/A"

    lines = [
        f"# {data['name']} ({data['ticker']})",
        f"*{data['sector']} · {data['industry']} · Data as of {data['data_date']}*",
        "",
        f"## {icon} Overall Signal: **{s['verdict']}** (Score: {s['score']})",
        "",
        *[f"- {sig}" for sig in s["signals"]],
        "",
        "---",
        "## 💰 Price Summary",
        "",
        f"| | |","|---|---|",
        f"| **Current Price** | {data['currency']} {_fv(data['price'])} |",
        f"| **Day Change** | {chg_str} |",
        f"| **52-Week High** | {_fv(data['52w_high'])} |",
        f"| **52-Week Low** | {_fv(data['52w_low'])} |",
        f"| **From 52W High** | {_fv(data['pct_from_52w_high'], 1)}% |",
        f"| **Market Cap** | {_fc(data.get('market_cap'))} |",
        f"| **Beta** | {_fv(data.get('beta'), 2)} |",
        f"| **Analyst Target** | {_fv(data.get('analyst_target'))} |",
        "",
        "---",
        "## 📊 Valuation Ratios",
        "",
        f"| Metric | Value | Context |","|--------|-------|---------|",
        f"| **P/E Ratio (TTM)** | {_fv(va['pe_ratio'],1)} | {_val_ctx('pe', va['pe_ratio'])} |",
        f"| **Forward P/E** | {_fv(va['forward_pe'],1)} | — |",
        f"| **Price-to-Sales (P/S)** | {_fv(va['ps_ratio'],1)} | {_val_ctx('ps', va['ps_ratio'])} |",
        f"| **Price-to-Book (P/B)** | {_fv(va['pb_ratio'],1)} | {_val_ctx('pb', va['pb_ratio'])} |",
        f"| **PEG Ratio** | {_fv(va['peg_ratio'],2)} | {_val_ctx('peg', va['peg_ratio'])} |",
        f"| **EV / EBITDA** | {_fv(va['ev_ebitda'],1)} | — |",
        "",
        "---",
        "## 📈 Profitability",
        "",
        f"| Metric | Value |","|--------|-------|",
        f"| **Net Profit Margin** | {_fp(pr['net_margin'])} |",
        f"| **Operating Margin** | {_fp(pr['operating_margin'])} |",
        f"| **Return on Equity (ROE)** | {_fp(pr['roe'])} |",
        f"| **Return on Assets (ROA)** | {_fp(pr['roa'])} |",
        "",
        "---",
        "## 🚀 Growth (YoY)",
        "",
        f"| Metric | Value |","|--------|-------|",
        f"| **Revenue Growth** | {_fp(gr['revenue_growth'])} |",
        f"| **EPS Growth** | {_fp(gr['eps_growth'])} |",
        "",
        "---",
        "## 🏦 Financial Health",
        "",
        f"| Metric | Value |","|--------|-------|",
        f"| **Debt / Equity** | {_fv(fh['debt_equity'],2)} |",
        f"| **Current Ratio** | {_fv(fh['current_ratio'],2)} |",
        "",
        "---",
        "## 💵 Dividends",
        "",
        f"| Metric | Value |","|--------|-------|",
        f"| **Dividend Yield** | {_fp(dv['yield'])} |",
        f"| **Payout Ratio** | {_fp(dv['payout_ratio'])} |",
        "",
        "---",
        "## 📉 Technical Indicators",
        "",
        f"| Indicator | Value | Signal |","|-----------|-------|--------|",
        f"| **RSI (14)** | {_fv(t['rsi_14'],1)} | {_rsi_lbl(t['rsi_14'])} |",
        f"| **MACD Histogram** | {_fv(t['macd_histogram'],4)} | {'Bullish momentum' if (t['macd_histogram'] or 0) > 0 else 'Bearish momentum'} |",
        f"| **SMA 20** | {_fv(t['sma_20'])} | Price {'above ✅' if (data['price'] or 0) > (t['sma_20'] or 0) else 'below ❌'} |",
        f"| **SMA 50** | {_fv(t['sma_50'])} | Price {'above ✅' if (data['price'] or 0) > (t['sma_50'] or 0) else 'below ❌'} |",
        f"| **SMA 200** | {_fv(t['sma_200'])} | Price {'above ✅' if (data['price'] or 0) > (t['sma_200'] or 0) else 'below ❌'} |",
        f"| **BB Upper** | {_fv(t['bb_upper'])} | — |",
        f"| **BB Lower** | {_fv(t['bb_lower'])} | — |",
        f"| **Volume Spike** | {_fv(t['volume_spike_ratio'])}x | {'Notable ⚡' if (t['volume_spike_ratio'] or 0) > 1.5 else 'Normal'} |",
        "",
        "---",
        "*⚠️ For informational purposes only. Not financial advice.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw stock deep-analysis (Alpha Vantage)")
    parser.add_argument("--ticker",  required=True, help="Ticker or comma-separated list")
    parser.add_argument("--period",  default="compact", choices=["compact","full"],
                        help="compact = last 100 days, full = up to 20 years")
    parser.add_argument("--mode",    default="single", choices=["single","compare"])
    parser.add_argument("--output",  default="markdown", choices=["markdown","json"])
    parser.add_argument("--api-key", dest="api_key", help="Alpha Vantage API key (or set ALPHA_VANTAGE_KEY env var)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.ticker.split(",")]

    results = []
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(1)   # Alpha Vantage free tier: ~5 req/min
        print(f"Fetching {ticker}...", file=sys.stderr)
        results.append(fetch_stock(ticker, args.period, args.api_key))

    if args.output == "json":
        out = results if len(results) > 1 else results[0]
        print(json.dumps(out, indent=2, default=str))
        return

    if args.mode == "compare" and len(results) > 1:
        print(f"# Stock Comparison\n")
        headers = ["Ticker","Price","Day%","RSI","P/E","P/S","P/B","ROE","Rev Growth","Signal"]
        rows = []
        for r in results:
            if "error" in r:
                rows.append([r.get("ticker","?"),"ERROR"]+["-"]*8)
            else:
                rows.append([
                    r["ticker"], f"${_fv(r['price'])}",
                    f"{float(r['change_pct']):+.2f}%" if r.get("change_pct") else "N/A",
                    _fv(r["technical"]["rsi_14"],1),
                    _fv(r["valuation"]["pe_ratio"],1),
                    _fv(r["valuation"]["ps_ratio"],1),
                    _fv(r["valuation"]["pb_ratio"],1),
                    _fp(r["profitability"]["roe"]),
                    _fp(r["growth"]["revenue_growth"]),
                    r["signal"]["verdict"],
                ])
        col_w = [max(len(h), max(len(row[i]) for row in rows)) for i,h in enumerate(headers)]
        row_str = lambda cells: "| "+" | ".join(c.ljust(col_w[i]) for i,c in enumerate(cells))+" |"
        print(row_str(headers))
        print("| "+" | ".join("-"*w for w in col_w)+" |")
        for row in rows: print(row_str(row))
        print()

    for r in results:
        print(format_report(r))
        if len(results) > 1: print("\n---\n")


if __name__ == "__main__":
    main()
