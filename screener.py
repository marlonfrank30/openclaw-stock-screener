#!/usr/bin/env python3
"""
screener.py — Batch fundamental + technical stock screener for OpenClaw.

Supported fundamental filters:
  Valuation:   --pe-max, --pe-min, --ps-max, --pb-max, --peg-max,
               --ev-ebitda-max, --price-fcf-max
  Profitability: --profit-margin-min, --roe-min, --roa-min, --gross-margin-min
  Growth:      --revenue-growth-min, --eps-growth-min, --earnings-growth-min
  Financial health: --debt-equity-max, --current-ratio-min, --quick-ratio-min
  Dividends:   --dividend-yield-min, --dividend-yield-max
  Technical:   --rsi-min, --rsi-max, --volume-spike, --above-sma50, --above-sma200

Presets: momentum | value | growth | dividend | quality | breakout | oversold_reversal

Usage:
  python3 screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL
  python3 screener.py --tickers AAPL,MSFT,NVDA --preset value
  python3 screener.py --tickers AAPL,MSFT,NVDA --pe-max 25 --ps-max 5 --roe-min 0.15
  python3 screener.py --tickers AAPL,MSFT,NVDA --output json
"""

import argparse
import json
import sys
import time
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np

from indicators import rsi, macd, sma, volume_spike, signal_summary, bollinger_bands


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

PRESETS = {
    "momentum": {
        "description": "Trending stocks with strong price action and volume",
        "rsi_min": 50, "rsi_max": 70,
        "require_above_sma50": True,
        "require_above_sma200": True,
        "volume_spike_min": 1.3,
        "require_bullish_macd": True,
    },
    "value": {
        "description": "Undervalued stocks by classic valuation metrics",
        "pe_max": 20,
        "ps_max": 3.0,
        "pb_max": 3.0,
        "peg_max": 1.5,
        "debt_equity_max": 1.0,
        "roe_min": 0.10,
    },
    "growth": {
        "description": "High-growth companies with strong revenue and earnings expansion",
        "revenue_growth_min": 0.15,
        "eps_growth_min": 0.15,
        "gross_margin_min": 0.30,
        "ps_max": 15.0,        # growth stocks command higher P/S
    },
    "quality": {
        "description": "Financially sound companies with consistent profitability",
        "roe_min": 0.15,
        "roa_min": 0.08,
        "profit_margin_min": 0.10,
        "gross_margin_min": 0.35,
        "current_ratio_min": 1.5,
        "debt_equity_max": 0.5,
    },
    "dividend": {
        "description": "Dividend-paying stocks with healthy yields and payout coverage",
        "dividend_yield_min": 0.02,
        "dividend_yield_max": 0.10,   # very high yield often signals distress
        "profit_margin_min": 0.08,
        "debt_equity_max": 1.5,
    },
    "breakout": {
        "description": "Stocks near 52-week highs with strong volume",
        "pct_from_52w_high_max": -2.0,
        "volume_spike_min": 2.0,
        "rsi_min": 55, "rsi_max": 75,
        "require_above_sma50": True,
    },
    "oversold_reversal": {
        "description": "Technically oversold stocks that may be due for a bounce",
        "rsi_max": 35,
        "require_near_bb_lower": True,
    },
}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_screen_data(ticker: str, period: str = "6mo") -> dict | None:
    """Fetch all technical and fundamental data needed for screening."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return None

        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass

        close = hist["Close"]
        volume = hist["Volume"]

        # Technical
        r       = rsi(close)
        m       = macd(close)
        s50     = sma(close, 50)
        s200    = sma(close, 200)
        vs      = volume_spike(volume)
        bb      = bollinger_bands(close)
        sigs    = signal_summary(close, volume)

        price        = close.iloc[-1]
        high_52w     = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
        low_52w      = close.rolling(252).min().iloc[-1] if len(close) >= 252 else close.min()
        pct_from_high = ((price - high_52w) / high_52w) * 100
        bb_lower     = bb["lower"].iloc[-1]
        near_bb_lower = price <= bb_lower * 1.03

        # Valuation ratios
        pe_ratio      = info.get("trailingPE")
        forward_pe    = info.get("forwardPE")
        ps_ratio      = info.get("priceToSalesTrailing12Months")
        pb_ratio      = info.get("priceToBook")
        peg_ratio     = info.get("pegRatio")
        ev_ebitda     = info.get("enterpriseToEbitda")
        price_fcf     = _calc_price_fcf(info)

        # Profitability
        profit_margin = info.get("profitMargins")
        gross_margin  = info.get("grossMargins")
        operating_margin = info.get("operatingMargins")
        roe           = info.get("returnOnEquity")
        roa           = info.get("returnOnAssets")

        # Growth
        revenue_growth   = info.get("revenueGrowth")
        eps_growth       = info.get("earningsGrowth")      # YoY quarterly
        earnings_growth  = info.get("earningsGrowth")

        # Financial health
        debt_equity      = info.get("debtToEquity")
        current_ratio    = info.get("currentRatio")
        quick_ratio      = info.get("quickRatio")
        free_cashflow    = info.get("freeCashflow")

        # Dividends
        dividend_yield   = info.get("dividendYield")
        payout_ratio     = info.get("payoutRatio")

        return {
            "ticker":       ticker.upper(),
            "name":         info.get("shortName", ticker.upper()),
            "sector":       info.get("sector", "N/A"),
            "industry":     info.get("industry", "N/A"),
            "price":        round(price, 2),
            "currency":     info.get("currency", "USD"),
            "market_cap":   info.get("marketCap"),

            # Technical
            "rsi":                  _r(r.iloc[-1]),
            "macd_histogram":       _r(m["histogram"].iloc[-1], 4),
            "above_sma50":          bool(price > s50.iloc[-1]) if not pd.isna(s50.iloc[-1]) else False,
            "above_sma200":         bool(price > s200.iloc[-1]) if not pd.isna(s200.iloc[-1]) else False,
            "volume_spike":         _r(vs.iloc[-1]),
            "pct_from_52w_high":    round(pct_from_high, 1),
            "near_bb_lower":        near_bb_lower,
            "signal_verdict":       sigs["verdict"],
            "signal_score":         sigs["score"],

            # Valuation
            "pe_ratio":     pe_ratio,
            "forward_pe":   forward_pe,
            "ps_ratio":     ps_ratio,
            "pb_ratio":     pb_ratio,
            "peg_ratio":    peg_ratio,
            "ev_ebitda":    ev_ebitda,
            "price_fcf":    price_fcf,

            # Profitability
            "profit_margin":     profit_margin,
            "gross_margin":      gross_margin,
            "operating_margin":  operating_margin,
            "roe":               roe,
            "roa":               roa,

            # Growth
            "revenue_growth":    revenue_growth,
            "eps_growth":        eps_growth,
            "earnings_growth":   earnings_growth,

            # Financial health
            "debt_equity":    debt_equity,
            "current_ratio":  current_ratio,
            "quick_ratio":    quick_ratio,
            "free_cashflow":  free_cashflow,

            # Dividends
            "dividend_yield": dividend_yield,
            "payout_ratio":   payout_ratio,

            "data_date": hist.index[-1].strftime("%Y-%m-%d"),
        }

    except Exception as e:
        print(f"Warning: failed to fetch {ticker}: {e}", file=sys.stderr)
        return None


def _r(v, decimals=2):
    """Round if not NaN, else None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return round(float(v), decimals)


def _calc_price_fcf(info: dict):
    """Estimate Price-to-Free-Cash-Flow from marketCap and freeCashflow."""
    mc  = info.get("marketCap")
    fcf = info.get("freeCashflow")
    if mc and fcf and fcf > 0:
        return round(mc / fcf, 2)
    return None


# ---------------------------------------------------------------------------
# Filter engine
# ---------------------------------------------------------------------------

# Maps filter key → (data_key, direction)
# direction: "max" means value must be <= threshold; "min" means >=
FILTER_MAP = {
    # Valuation
    "pe_max":           ("pe_ratio",        "max"),
    "pe_min":           ("pe_ratio",        "min"),
    "ps_max":           ("ps_ratio",        "max"),
    "pb_max":           ("pb_ratio",        "max"),
    "peg_max":          ("peg_ratio",       "max"),
    "ev_ebitda_max":    ("ev_ebitda",       "max"),
    "price_fcf_max":    ("price_fcf",       "max"),
    # Profitability
    "profit_margin_min":    ("profit_margin",    "min"),
    "gross_margin_min":     ("gross_margin",     "min"),
    "roe_min":              ("roe",              "min"),
    "roa_min":              ("roa",              "min"),
    # Growth
    "revenue_growth_min":   ("revenue_growth",   "min"),
    "eps_growth_min":       ("eps_growth",       "min"),
    "earnings_growth_min":  ("earnings_growth",  "min"),
    # Financial health
    "debt_equity_max":      ("debt_equity",      "max"),
    "current_ratio_min":    ("current_ratio",    "min"),
    "quick_ratio_min":      ("quick_ratio",      "min"),
    # Dividends
    "dividend_yield_min":   ("dividend_yield",   "min"),
    "dividend_yield_max":   ("dividend_yield",   "max"),
    # Technical — numeric
    "rsi_min":              ("rsi",              "min"),
    "rsi_max":              ("rsi",              "max"),
    "volume_spike_min":     ("volume_spike",     "min"),
    "pct_from_52w_high_max":("pct_from_52w_high","max"),
}

def apply_filters(data: dict, filters: dict) -> bool:
    """Return True if stock passes all active filters."""
    for filter_key, threshold in filters.items():
        # Numeric filters via FILTER_MAP
        if filter_key in FILTER_MAP:
            data_key, direction = FILTER_MAP[filter_key]
            val = data.get(data_key)
            if val is None:
                return False          # can't verify — exclude
            if direction == "max" and val > threshold:
                return False
            if direction == "min" and val < threshold:
                return False

        # Boolean / special filters
        elif filter_key == "require_above_sma50" and threshold:
            if not data.get("above_sma50"):
                return False
        elif filter_key == "require_above_sma200" and threshold:
            if not data.get("above_sma200"):
                return False
        elif filter_key == "require_bullish_macd" and threshold:
            if (data.get("macd_histogram") or 0) <= 0:
                return False
        elif filter_key == "require_near_bb_lower" and threshold:
            if not data.get("near_bb_lower"):
                return False

    return True


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(v, decimals=2):
    if v is None: return "N/A"
    return f"{v:.{decimals}f}"

def _fmt_pct(v):
    if v is None: return "N/A"
    return f"{v*100:.1f}%"

def _fmt_cap(v):
    if v is None: return "N/A"
    if v >= 1e12: return f"${v/1e12:.1f}T"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"

VERDICT_ICON = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_markdown_table(passed: list, total: int, filters: dict):
    print("# Stock Screener Results\n")
    print(f"**Scanned:** {total} tickers | **Passed filters:** {len(passed)}\n")

    if filters:
        print("**Active filters:**")
        for k, v in filters.items():
            print(f"- `{k}`: {v}")
        print()

    if not passed:
        print("*No stocks passed the current filters. Try relaxing your criteria.*")
        return

    headers = [
        "Rank", "Ticker", "Name", "Price", "Signal",
        "P/E", "P/S", "P/B", "PEG", "EV/EBITDA",
        "P/FCF", "ROE", "Gross Margin", "Rev Growth", "D/E", "Div Yield",
        "RSI", "From 52W High"
    ]
    rows = []
    for i, r in enumerate(passed, 1):
        icon = VERDICT_ICON.get(r["signal_verdict"], "⚪")
        rows.append([
            str(i),
            r["ticker"],
            r["name"][:18],
            f"${r['price']}",
            f"{icon} {r['signal_verdict']}",
            _fmt(r["pe_ratio"], 1),
            _fmt(r["ps_ratio"], 1),
            _fmt(r["pb_ratio"], 1),
            _fmt(r["peg_ratio"], 1),
            _fmt(r["ev_ebitda"], 1),
            _fmt(r["price_fcf"], 1),
            _fmt_pct(r["roe"]),
            _fmt_pct(r["gross_margin"]),
            _fmt_pct(r["revenue_growth"]),
            _fmt(r["debt_equity"], 1),
            _fmt_pct(r["dividend_yield"]),
            _fmt(r["rsi"], 1),
            f"{r['pct_from_52w_high']:+.1f}%",
        ])

    col_w = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    def row_str(cells):
        return "| " + " | ".join(c.ljust(col_w[i]) for i, c in enumerate(cells)) + " |"

    print(row_str(headers))
    print("| " + " | ".join("-" * w for w in col_w) + " |")
    for row in rows:
        print(row_str(row))

    print("\n*Ranked by composite signal score. Fundamental data via Yahoo Finance.*")
    print("*⚠️ For informational purposes only. Not financial advice.*")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw fundamental + technical stock screener",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets: momentum | value | growth | quality | dividend | breakout | oversold_reversal

Examples:
  python3 screener.py --tickers AAPL,MSFT,NVDA --preset value
  python3 screener.py --tickers AAPL,MSFT,NVDA --pe-max 25 --ps-max 5 --roe-min 0.15
  python3 screener.py --tickers AAPL,MSFT,NVDA --preset growth --output json
        """
    )
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers")
    parser.add_argument("--period", default="6mo", help="Price history period: 1mo 3mo 6mo 1y 2y")
    parser.add_argument("--preset", choices=list(PRESETS.keys()))

    # Valuation
    g_val = parser.add_argument_group("Valuation filters")
    g_val.add_argument("--pe-max",        type=float, help="Max trailing P/E ratio")
    g_val.add_argument("--pe-min",        type=float, help="Min trailing P/E ratio")
    g_val.add_argument("--ps-max",        type=float, help="Max Price-to-Sales ratio")
    g_val.add_argument("--pb-max",        type=float, help="Max Price-to-Book ratio")
    g_val.add_argument("--peg-max",       type=float, help="Max PEG ratio")
    g_val.add_argument("--ev-ebitda-max", type=float, help="Max EV/EBITDA")
    g_val.add_argument("--price-fcf-max", type=float, help="Max Price-to-Free-Cash-Flow")

    # Profitability
    g_prof = parser.add_argument_group("Profitability filters")
    g_prof.add_argument("--profit-margin-min", type=float, help="Min net profit margin (0–1)")
    g_prof.add_argument("--gross-margin-min",  type=float, help="Min gross margin (0–1)")
    g_prof.add_argument("--roe-min",           type=float, help="Min Return on Equity (0–1)")
    g_prof.add_argument("--roa-min",           type=float, help="Min Return on Assets (0–1)")

    # Growth
    g_growth = parser.add_argument_group("Growth filters")
    g_growth.add_argument("--revenue-growth-min",  type=float, help="Min revenue growth YoY (0–1)")
    g_growth.add_argument("--eps-growth-min",      type=float, help="Min EPS growth YoY (0–1)")
    g_growth.add_argument("--earnings-growth-min", type=float, help="Min earnings growth YoY (0–1)")

    # Financial health
    g_health = parser.add_argument_group("Financial health filters")
    g_health.add_argument("--debt-equity-max",   type=float, help="Max Debt/Equity ratio")
    g_health.add_argument("--current-ratio-min", type=float, help="Min current ratio")
    g_health.add_argument("--quick-ratio-min",   type=float, help="Min quick ratio")

    # Dividends
    g_div = parser.add_argument_group("Dividend filters")
    g_div.add_argument("--dividend-yield-min", type=float, help="Min dividend yield (0–1, e.g. 0.02 = 2%%)")
    g_div.add_argument("--dividend-yield-max", type=float, help="Max dividend yield (0–1)")

    # Technical
    g_tech = parser.add_argument_group("Technical filters")
    g_tech.add_argument("--rsi-min",       type=float)
    g_tech.add_argument("--rsi-max",       type=float)
    g_tech.add_argument("--volume-spike",  type=float, dest="volume_spike_min", help="Min volume spike ratio (e.g. 1.5)")
    g_tech.add_argument("--above-sma50",   action="store_true", dest="require_above_sma50")
    g_tech.add_argument("--above-sma200",  action="store_true", dest="require_above_sma200")

    parser.add_argument("--output", default="markdown", choices=["markdown", "json"])
    args = parser.parse_args()

    # Build filters: start with preset, then override with CLI args
    filters = {}
    if args.preset:
        filters.update(PRESETS[args.preset])
        print(f"Using preset '{args.preset}': {PRESETS[args.preset]['description']}", file=sys.stderr)

    cli_filter_keys = [
        "pe_max", "pe_min", "ps_max", "pb_max", "peg_max", "ev_ebitda_max", "price_fcf_max",
        "profit_margin_min", "gross_margin_min", "roe_min", "roa_min",
        "revenue_growth_min", "eps_growth_min", "earnings_growth_min",
        "debt_equity_max", "current_ratio_min", "quick_ratio_min",
        "dividend_yield_min", "dividend_yield_max",
        "rsi_min", "rsi_max", "volume_spike_min",
        "require_above_sma50", "require_above_sma200",
    ]
    for key in cli_filter_keys:
        val = getattr(args, key, None)
        if val:
            filters[key] = val

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    all_data = []
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(0.5)
        print(f"Fetching {ticker}...", file=sys.stderr)
        d = fetch_screen_data(ticker, args.period)
        if d:
            all_data.append(d)

    # Filter and rank by composite signal score
    passed = [d for d in all_data if apply_filters(d, filters)]
    passed.sort(key=lambda x: x["signal_score"], reverse=True)

    if args.output == "json":
        print(json.dumps({
            "total": len(all_data),
            "passed": len(passed),
            "filters": filters,
            "results": passed
        }, indent=2, default=str))
        return

    print_markdown_table(passed, len(all_data), filters)


if __name__ == "__main__":
    main()
