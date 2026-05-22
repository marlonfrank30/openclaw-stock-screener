#!/usr/bin/env python3
"""
analyze_stock.py — Single or multi-stock deep analysis for OpenClaw.

Covers:
  Valuation:     P/E, Forward P/E, P/S, P/B, PEG, EV/EBITDA, Price/FCF
  Profitability: Net margin, Gross margin, Operating margin, ROE, ROA
  Growth:        Revenue growth, EPS growth, Earnings growth
  Health:        Debt/Equity, Current ratio, Quick ratio, Free cash flow
  Dividends:     Yield, Payout ratio
  Technical:     RSI, MACD, Bollinger Bands, SMA 20/50/200, Volume spike

Usage:
  python3 analyze_stock.py --ticker AAPL
  python3 analyze_stock.py --ticker AAPL --period 1y
  python3 analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare
  python3 analyze_stock.py --ticker AAPL --output json
"""

import argparse
import json
import sys
import time
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd

from indicators import rsi, macd, bollinger_bands, sma, volume_spike, signal_summary


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_stock(ticker: str, period: str = "6mo") -> dict:
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return {"error": f"No data found for {ticker}. It may be delisted or invalid."}

    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    close  = hist["Close"]
    volume = hist["Volume"]

    # Technical
    r    = rsi(close)
    m    = macd(close)
    bb   = bollinger_bands(close)
    s20  = sma(close, 20)
    s50  = sma(close, 50)
    s200 = sma(close, 200)
    vs   = volume_spike(volume)
    sigs = signal_summary(close, volume)

    price        = close.iloc[-1]
    prev_close   = close.iloc[-2] if len(close) > 1 else price
    day_chg_pct  = ((price - prev_close) / prev_close) * 100
    high_52w     = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
    low_52w      = close.rolling(252).min().iloc[-1] if len(close) >= 252 else close.min()
    pct_from_high = ((price - high_52w) / high_52w) * 100

    # Price/FCF calculation
    mc  = info.get("marketCap")
    fcf = info.get("freeCashflow")
    price_fcf = round(mc / fcf, 2) if mc and fcf and fcf > 0 else None

    def _r(v, d=2):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return round(float(v), d)

    return {
        "ticker":   ticker.upper(),
        "name":     info.get("longName", ticker.upper()),
        "sector":   info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "price":    round(price, 2),
        "currency": info.get("currency", "USD"),
        "change_pct_day": round(day_chg_pct, 2),
        "52w_high": round(high_52w, 2),
        "52w_low":  round(low_52w, 2),
        "pct_from_52w_high": round(pct_from_high, 1),
        "market_cap": mc,

        "technical": {
            "rsi_14":           _r(r.iloc[-1], 1),
            "macd_line":        _r(m["macd"].iloc[-1], 4),
            "macd_signal":      _r(m["signal"].iloc[-1], 4),
            "macd_histogram":   _r(m["histogram"].iloc[-1], 4),
            "sma_20":           _r(s20.iloc[-1]),
            "sma_50":           _r(s50.iloc[-1]),
            "sma_200":          _r(s200.iloc[-1]),
            "bb_upper":         _r(bb["upper"].iloc[-1]),
            "bb_lower":         _r(bb["lower"].iloc[-1]),
            "volume_spike_ratio": _r(vs.iloc[-1]),
        },

        "valuation": {
            "pe_ratio":    info.get("trailingPE"),
            "forward_pe":  info.get("forwardPE"),
            "ps_ratio":    info.get("priceToSalesTrailing12Months"),
            "pb_ratio":    info.get("priceToBook"),
            "peg_ratio":   info.get("pegRatio"),
            "ev_ebitda":   info.get("enterpriseToEbitda"),
            "price_fcf":   price_fcf,
        },

        "profitability": {
            "net_margin":       info.get("profitMargins"),
            "gross_margin":     info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "roe":              info.get("returnOnEquity"),
            "roa":              info.get("returnOnAssets"),
        },

        "growth": {
            "revenue_growth":  info.get("revenueGrowth"),
            "eps_growth":      info.get("earningsGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
        },

        "financial_health": {
            "debt_equity":   info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio":   info.get("quickRatio"),
            "free_cashflow": info.get("freeCashflow"),
        },

        "dividends": {
            "yield":        info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
        },

        "signal":    sigs,
        "data_date": hist.index[-1].strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fv(v, d=2):
    return "N/A" if v is None else f"{v:,.{d}f}"

def _fp(v):
    return "N/A" if v is None else f"{v*100:.1f}%"

def _fc(v):
    if v is None: return "N/A"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def _rsi_label(v):
    if v is None: return "N/A"
    if v < 30: return "Oversold 🟢"
    if v > 70: return "Overbought 🔴"
    return "Neutral"

def _val_note(metric, value):
    """Contextual interpretation for key valuation ratios."""
    if value is None:
        return ""
    notes = {
        "pe":  [(0,10,"Potentially undervalued"),(10,20,"Fairly valued"),(20,30,"Growth premium"),(30,999,"High / speculative")],
        "ps":  [(0,1,"Very cheap"),(1,3,"Reasonable"),(3,8,"Growth premium"),(8,999,"Expensive")],
        "pb":  [(0,1,"Below book"),(1,3,"Reasonable"),(3,8,"Premium"),(8,999,"High premium")],
        "peg": [(0,1,"Undervalued vs growth"),(1,2,"Fair"),(2,999,"Overvalued vs growth")],
    }
    ranges = notes.get(metric, [])
    for lo, hi, label in ranges:
        if lo <= value < hi:
            return label
    return ""

def format_markdown_report(data: dict) -> str:
    if "error" in data:
        return f"## ❌ Error\n\n{data['error']}"

    t  = data["technical"]
    va = data["valuation"]
    pr = data["profitability"]
    gr = data["growth"]
    fh = data["financial_health"]
    dv = data["dividends"]
    s  = data["signal"]

    icon = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(s["verdict"], "⚪")

    lines = [
        f"# {data['name']} ({data['ticker']})",
        f"*{data['sector']} · {data['industry']} · Data as of {data['data_date']}*",
        "",
        f"## {icon} Overall Signal: **{s['verdict']}** (Score: {s['score']})",
        "",
        *[f"- {sig}" for sig in s["signals"]],
        "",
        "---",
        "",
        "## 💰 Price Summary",
        "",
        f"| | |",
        f"|---|---|",
        f"| **Current Price** | {data['currency']} {data['price']} |",
        f"| **Day Change** | {data['change_pct_day']:+.2f}% |",
        f"| **52-Week High** | {data['52w_high']} |",
        f"| **52-Week Low** | {data['52w_low']} |",
        f"| **From 52W High** | {data['pct_from_52w_high']:+.1f}% |",
        f"| **Market Cap** | {_fc(data.get('market_cap'))} |",
        "",
        "---",
        "",
        "## 📊 Valuation Ratios",
        "",
        f"| Metric | Value | Context |",
        f"|--------|-------|---------|",
        f"| **P/E Ratio (TTM)** | {_fv(va['pe_ratio'],1)} | {_val_note('pe', va['pe_ratio'])} |",
        f"| **Forward P/E** | {_fv(va['forward_pe'],1)} | — |",
        f"| **Price-to-Sales (P/S)** | {_fv(va['ps_ratio'],1)} | {_val_note('ps', va['ps_ratio'])} |",
        f"| **Price-to-Book (P/B)** | {_fv(va['pb_ratio'],1)} | {_val_note('pb', va['pb_ratio'])} |",
        f"| **PEG Ratio** | {_fv(va['peg_ratio'],2)} | {_val_note('peg', va['peg_ratio'])} |",
        f"| **EV / EBITDA** | {_fv(va['ev_ebitda'],1)} | — |",
        f"| **Price / Free Cash Flow** | {_fv(va['price_fcf'],1)} | — |",
        "",
        "---",
        "",
        "## 📈 Profitability",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Net Profit Margin** | {_fp(pr['net_margin'])} |",
        f"| **Gross Margin** | {_fp(pr['gross_margin'])} |",
        f"| **Operating Margin** | {_fp(pr['operating_margin'])} |",
        f"| **Return on Equity (ROE)** | {_fp(pr['roe'])} |",
        f"| **Return on Assets (ROA)** | {_fp(pr['roa'])} |",
        "",
        "---",
        "",
        "## 🚀 Growth",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Revenue Growth (YoY)** | {_fp(gr['revenue_growth'])} |",
        f"| **EPS Growth (YoY)** | {_fp(gr['eps_growth'])} |",
        f"| **Earnings Growth (YoY)** | {_fp(gr['earnings_growth'])} |",
        "",
        "---",
        "",
        "## 🏦 Financial Health",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Debt / Equity** | {_fv(fh['debt_equity'],2)} |",
        f"| **Current Ratio** | {_fv(fh['current_ratio'],2)} |",
        f"| **Quick Ratio** | {_fv(fh['quick_ratio'],2)} |",
        f"| **Free Cash Flow** | {_fc(fh['free_cashflow'])} |",
        "",
        "---",
        "",
        "## 💵 Dividends",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Dividend Yield** | {_fp(dv['yield'])} |",
        f"| **Payout Ratio** | {_fp(dv['payout_ratio'])} |",
        "",
        "---",
        "",
        "## 📉 Technical Indicators",
        "",
        f"| Indicator | Value | Signal |",
        f"|-----------|-------|--------|",
        f"| **RSI (14)** | {_fv(t['rsi_14'],1)} | {_rsi_label(t['rsi_14'])} |",
        f"| **MACD Histogram** | {_fv(t['macd_histogram'],4)} | {'Bullish momentum' if (t['macd_histogram'] or 0) > 0 else 'Bearish momentum'} |",
        f"| **SMA 20** | {_fv(t['sma_20'])} | Price {'above ✅' if data['price'] > (t['sma_20'] or 0) else 'below ❌'} |",
        f"| **SMA 50** | {_fv(t['sma_50'])} | Price {'above ✅' if data['price'] > (t['sma_50'] or 0) else 'below ❌'} |",
        f"| **SMA 200** | {_fv(t['sma_200'])} | Price {'above ✅' if data['price'] > (t['sma_200'] or 0) else 'below ❌'} |",
        f"| **Bollinger Upper** | {_fv(t['bb_upper'])} | — |",
        f"| **Bollinger Lower** | {_fv(t['bb_lower'])} | — |",
        f"| **Volume Spike** | {_fv(t['volume_spike_ratio'])}x | {'Notable ⚡' if (t['volume_spike_ratio'] or 0) > 1.5 else 'Normal'} |",
        "",
        "---",
        "",
        "*⚠️ This analysis is for informational purposes only and does not constitute financial advice.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw stock deep-analysis")
    parser.add_argument("--ticker", required=True, help="Ticker or comma-separated list")
    parser.add_argument("--period", default="6mo", choices=["1mo","3mo","6mo","1y","2y","5y"])
    parser.add_argument("--mode",   default="single", choices=["single","compare"])
    parser.add_argument("--output", default="markdown", choices=["markdown","json"])
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.ticker.split(",")]
    results = []
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(0.5)
        results.append(fetch_stock(ticker, args.period))

    if args.output == "json":
        out = results if len(results) > 1 else results[0]
        print(json.dumps(out, indent=2, default=str))
        return

    if args.mode == "compare" and len(results) > 1:
        print(f"# Stock Comparison ({args.period})\n")
        headers = ["Ticker","Price","Day%","RSI","P/E","P/S","P/B","PEG","ROE","Rev Growth","Signal"]
        rows = []
        for r in results:
            if "error" in r:
                rows.append([r.get("ticker","?"), "ERROR"] + ["-"]*9)
            else:
                rows.append([
                    r["ticker"],
                    f"${r['price']}",
                    f"{r['change_pct_day']:+.2f}%",
                    _fv(r["technical"]["rsi_14"],1),
                    _fv(r["valuation"]["pe_ratio"],1),
                    _fv(r["valuation"]["ps_ratio"],1),
                    _fv(r["valuation"]["pb_ratio"],1),
                    _fv(r["valuation"]["peg_ratio"],2),
                    _fp(r["profitability"]["roe"]),
                    _fp(r["growth"]["revenue_growth"]),
                    r["signal"]["verdict"],
                ])
        col_w = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
        row_str = lambda cells: "| " + " | ".join(c.ljust(col_w[i]) for i,c in enumerate(cells)) + " |"
        print(row_str(headers))
        print("| " + " | ".join("-"*w for w in col_w) + " |")
        for row in rows:
            print(row_str(row))
        print()

    for r in results:
        print(format_markdown_report(r))
        if len(results) > 1:
            print("\n---\n")


if __name__ == "__main__":
    main()
