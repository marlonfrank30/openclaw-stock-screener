#!/usr/bin/env python3
"""
screener.py — Batch fundamental + technical stock screener for OpenClaw.
Uses Alpha Vantage API (works from server/datacenter IPs).

Setup:
  export ALPHA_VANTAGE_KEY="your_key_here"

⚠️  Free tier: 25 requests/day, ~5/minute.
    Each ticker uses 2 API calls (quote + overview). Plan accordingly.
    For large lists, consider upgrading at alphavantage.co.

Presets: momentum | value | growth | quality | dividend | breakout | oversold_reversal

Usage:
  python3 screener.py --tickers AAPL,MSFT,NVDA
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

import pandas as pd

from av_client import get_api_key, fetch_quote, fetch_daily, fetch_overview
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
        "pe_max": 20, "ps_max": 3.0, "pb_max": 3.0,
        "peg_max": 1.5, "debt_equity_max": 1.0, "roe_min": 0.10,
    },
    "growth": {
        "description": "High-growth companies with strong revenue and earnings expansion",
        "revenue_growth_min": 0.15, "eps_growth_min": 0.15, "ps_max": 15.0,
    },
    "quality": {
        "description": "Financially sound companies with consistent profitability",
        "roe_min": 0.15, "roa_min": 0.08,
        "profit_margin_min": 0.10, "current_ratio_min": 1.5, "debt_equity_max": 0.5,
    },
    "dividend": {
        "description": "Dividend-paying stocks with healthy yields",
        "dividend_yield_min": 0.02, "dividend_yield_max": 0.10,
        "profit_margin_min": 0.08, "debt_equity_max": 1.5,
    },
    "breakout": {
        "description": "Stocks near 52-week highs with strong volume",
        "pct_from_52w_high_max": -2.0,
        "volume_spike_min": 2.0, "rsi_min": 55, "rsi_max": 75,
        "require_above_sma50": True,
    },
    "oversold_reversal": {
        "description": "Technically oversold stocks due for a bounce",
        "rsi_max": 35, "require_near_bb_lower": True,
    },
}

FILTER_MAP = {
    "pe_max":               ("pe_ratio",        "max"),
    "pe_min":               ("pe_ratio",        "min"),
    "ps_max":               ("ps_ratio",        "max"),
    "pb_max":               ("pb_ratio",        "max"),
    "peg_max":              ("peg_ratio",       "max"),
    "ev_ebitda_max":        ("ev_ebitda",       "max"),
    "profit_margin_min":    ("profit_margin",   "min"),
    "roe_min":              ("roe",             "min"),
    "roa_min":              ("roa",             "min"),
    "revenue_growth_min":   ("revenue_growth",  "min"),
    "eps_growth_min":       ("eps_growth",      "min"),
    "debt_equity_max":      ("debt_equity",     "max"),
    "current_ratio_min":    ("current_ratio",   "min"),
    "dividend_yield_min":   ("dividend_yield",  "min"),
    "dividend_yield_max":   ("dividend_yield",  "max"),
    "rsi_min":              ("rsi",             "min"),
    "rsi_max":              ("rsi",             "max"),
    "volume_spike_min":     ("volume_spike",    "min"),
    "pct_from_52w_high_max":("pct_from_52w_high","max"),
}


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_screen_data(ticker: str, api_key: str) -> dict | None:
    try:
        quote    = fetch_quote(ticker, api_key)
        if not quote:
            return None
        time.sleep(0.8)
        overview = fetch_overview(ticker, api_key)
        time.sleep(0.8)
        hist     = fetch_daily(ticker, api_key, outputsize="compact")
        if hist.empty:
            return None

        close  = hist["close"]
        volume = hist["volume"]

        r    = rsi(close)
        m    = macd(close)
        s50  = sma(close, 50)
        s200 = sma(close, 200)
        vs   = volume_spike(volume)
        bb   = bollinger_bands(close)
        sigs = signal_summary(close, volume)

        price    = quote.get("price") or close.iloc[-1]
        high_52w = overview.get("52w_high") or close.max()
        low_52w  = overview.get("52w_low")  or close.min()
        pct_high = round(((price - high_52w) / high_52w) * 100, 1) if high_52w else None

        sma50_val  = overview.get("50d_ma") or (s50.iloc[-1] if not pd.isna(s50.iloc[-1]) else None)
        sma200_val = overview.get("200d_ma") or (s200.iloc[-1] if not pd.isna(s200.iloc[-1]) else None)

        bb_lower     = bb["lower"].iloc[-1]
        near_bb_lower = price <= bb_lower * 1.03 if not pd.isna(bb_lower) else False

        def _r(v, d=2):
            if v is None or (isinstance(v, float) and pd.isna(v)): return None
            return round(float(v), d)

        return {
            "ticker":   ticker.upper(),
            "name":     overview.get("name", ticker.upper()),
            "sector":   overview.get("sector", "N/A"),
            "price":    price,
            # Technical
            "rsi":              _r(r.iloc[-1], 1),
            "macd_histogram":   _r(m["histogram"].iloc[-1], 4),
            "above_sma50":      bool(price > sma50_val) if sma50_val else False,
            "above_sma200":     bool(price > sma200_val) if sma200_val else False,
            "volume_spike":     _r(vs.iloc[-1]),
            "pct_from_52w_high": pct_high,
            "near_bb_lower":    near_bb_lower,
            "signal_verdict":   sigs["verdict"],
            "signal_score":     sigs["score"],
            # Fundamentals
            "pe_ratio":         overview.get("pe_ratio"),
            "ps_ratio":         overview.get("ps_ratio"),
            "pb_ratio":         overview.get("pb_ratio"),
            "peg_ratio":        overview.get("peg_ratio"),
            "ev_ebitda":        overview.get("ev_ebitda"),
            "profit_margin":    overview.get("profit_margin"),
            "roe":              overview.get("roe"),
            "roa":              overview.get("roa"),
            "revenue_growth":   overview.get("revenue_growth"),
            "eps_growth":       overview.get("eps_growth"),
            "debt_equity":      overview.get("debt_equity"),
            "current_ratio":    overview.get("current_ratio"),
            "dividend_yield":   overview.get("dividend_yield"),
            "market_cap":       overview.get("market_cap"),
        }
    except Exception as e:
        print(f"Warning: failed to fetch {ticker}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Filter engine
# ---------------------------------------------------------------------------

def apply_filters(data: dict, filters: dict) -> bool:
    for fkey, threshold in filters.items():
        if fkey in FILTER_MAP:
            dkey, direction = FILTER_MAP[fkey]
            val = data.get(dkey)
            if val is None:
                return False
            if direction == "max" and val > threshold: return False
            if direction == "min" and val < threshold: return False
        elif fkey == "require_above_sma50"    and threshold and not data.get("above_sma50"):    return False
        elif fkey == "require_above_sma200"   and threshold and not data.get("above_sma200"):   return False
        elif fkey == "require_bullish_macd"   and threshold and (data.get("macd_histogram") or 0) <= 0: return False
        elif fkey == "require_near_bb_lower"  and threshold and not data.get("near_bb_lower"):  return False
    return True


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _fv(v, d=2):  return "N/A" if v is None else f"{v:.{d}f}"
def _fp(v):
    if v is None: return "N/A"
    pct = v if abs(v) > 1 else v * 100
    return f"{pct:.1f}%"
def _fc(v):
    if v is None: return "N/A"
    if v >= 1e12: return f"${v/1e12:.1f}T"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    return f"${v/1e6:.0f}M"

ICON = {"BULLISH":"🟢","BEARISH":"🔴","NEUTRAL":"🟡"}

def print_table(passed: list, total: int, filters: dict):
    print("# Stock Screener Results\n")
    print(f"**Scanned:** {total} tickers | **Passed filters:** {len(passed)}\n")

    if filters:
        active = {k:v for k,v in filters.items() if k != "description"}
        print("**Active filters:**")
        for k, v in active.items(): print(f"- `{k}`: {v}")
        print()

    if not passed:
        print("*No stocks passed the current filters. Try relaxing your criteria.*")
        return

    headers = ["Rank","Ticker","Name","Price","Signal","P/E","P/S","P/B","ROE","Rev Growth","D/E","Div Yield","RSI","From 52W High"]
    rows = []
    for i, r in enumerate(passed, 1):
        rows.append([
            str(i), r["ticker"], r["name"][:18], f"${_fv(r['price'])}",
            f"{ICON.get(r['signal_verdict'],'⚪')} {r['signal_verdict']}",
            _fv(r["pe_ratio"],1), _fv(r["ps_ratio"],1), _fv(r["pb_ratio"],1),
            _fp(r["roe"]), _fp(r["revenue_growth"]),
            _fv(r["debt_equity"],1), _fp(r["dividend_yield"]),
            _fv(r["rsi"],1),
            f"{r['pct_from_52w_high']:+.1f}%" if r["pct_from_52w_high"] is not None else "N/A",
        ])

    col_w = [max(len(h), max(len(row[i]) for row in rows)) for i,h in enumerate(headers)]
    row_str = lambda cells: "| "+" | ".join(c.ljust(col_w[i]) for i,c in enumerate(cells))+" |"
    print(row_str(headers))
    print("| "+" | ".join("-"*w for w in col_w)+" |")
    for row in rows: print(row_str(row))
    print("\n*Ranked by composite signal score. Data via Alpha Vantage.*")
    print("*⚠️ For informational purposes only. Not financial advice.*")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw stock screener (Alpha Vantage)")
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--preset",  choices=list(PRESETS.keys()))
    parser.add_argument("--api-key", dest="api_key")
    parser.add_argument("--output",  default="markdown", choices=["markdown","json"])

    g = parser.add_argument_group("Valuation")
    g.add_argument("--pe-max",        type=float)
    g.add_argument("--pe-min",        type=float)
    g.add_argument("--ps-max",        type=float)
    g.add_argument("--pb-max",        type=float)
    g.add_argument("--peg-max",       type=float)
    g.add_argument("--ev-ebitda-max", type=float)

    g2 = parser.add_argument_group("Profitability / Growth / Health")
    g2.add_argument("--profit-margin-min",  type=float)
    g2.add_argument("--roe-min",            type=float)
    g2.add_argument("--roa-min",            type=float)
    g2.add_argument("--revenue-growth-min", type=float)
    g2.add_argument("--eps-growth-min",     type=float)
    g2.add_argument("--debt-equity-max",    type=float)
    g2.add_argument("--current-ratio-min",  type=float)
    g2.add_argument("--dividend-yield-min", type=float)
    g2.add_argument("--dividend-yield-max", type=float)

    g3 = parser.add_argument_group("Technical")
    g3.add_argument("--rsi-min",      type=float)
    g3.add_argument("--rsi-max",      type=float)
    g3.add_argument("--volume-spike", type=float, dest="volume_spike_min")
    g3.add_argument("--above-sma50",  action="store_true", dest="require_above_sma50")
    g3.add_argument("--above-sma200", action="store_true", dest="require_above_sma200")

    args = parser.parse_args()
    key  = get_api_key(args.api_key)

    filters = {}
    if args.preset:
        filters.update(PRESETS[args.preset])
        print(f"Preset '{args.preset}': {PRESETS[args.preset]['description']}", file=sys.stderr)

    cli_keys = [
        "pe_max","pe_min","ps_max","pb_max","peg_max","ev_ebitda_max",
        "profit_margin_min","roe_min","roa_min","revenue_growth_min","eps_growth_min",
        "debt_equity_max","current_ratio_min","dividend_yield_min","dividend_yield_max",
        "rsi_min","rsi_max","volume_spike_min","require_above_sma50","require_above_sma200",
    ]
    for k in cli_keys:
        v = getattr(args, k, None)
        if v: filters[k] = v

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    print(f"Screening {len(tickers)} tickers (2 API calls each — please wait)...", file=sys.stderr)

    all_data = []
    for ticker in tickers:
        d = fetch_screen_data(ticker, key)
        if d: all_data.append(d)

    passed = [d for d in all_data if apply_filters(d, filters)]
    passed.sort(key=lambda x: x["signal_score"], reverse=True)

    if args.output == "json":
        print(json.dumps({"total":len(all_data),"passed":len(passed),"results":passed}, indent=2, default=str))
        return

    print_table(passed, len(all_data), filters)


if __name__ == "__main__":
    main()
