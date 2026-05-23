"""
av_client.py — Alpha Vantage API client for OpenClaw stock screener.

Replaces yfinance with Alpha Vantage, which works reliably from server/datacenter IPs.

Set your API key in one of two ways:
  1. Environment variable:  export ALPHA_VANTAGE_KEY="YOUR_KEY"
  2. Pass directly:         AV_KEY = "YOUR_KEY" in your script

Free tier: 25 requests/day. Premium tiers available at alphavantage.co.
"""

import os
import time
import requests
import pandas as pd

BASE_URL = "https://www.alphavantage.co/query"

# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

def get_api_key(key: str = None) -> str:
    k = key or os.environ.get("ALPHA_VANTAGE_KEY") or os.environ.get("AV_KEY")
    if not k:
        raise EnvironmentError(
            "Alpha Vantage API key not found.\n"
            "Set it with: export ALPHA_VANTAGE_KEY='your_key'\n"
            "Get a free key at: https://www.alphavantage.co/support/#api-key"
        )
    return k


# ---------------------------------------------------------------------------
# Raw API calls
# ---------------------------------------------------------------------------

def _get(params: dict, api_key: str) -> dict:
    params["apikey"] = api_key
    r = requests.get(BASE_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "Note" in data:
        raise RuntimeError("Alpha Vantage rate limit reached. Wait 1 minute or upgrade your plan.")
    if "Information" in data:
        raise RuntimeError(f"Alpha Vantage API message: {data['Information']}")
    return data


def fetch_quote(symbol: str, api_key: str) -> dict:
    """Current price, volume, change. Fast — 1 API call."""
    data = _get({"function": "GLOBAL_QUOTE", "symbol": symbol}, api_key)
    q = data.get("Global Quote", {})
    if not q:
        return {}
    return {
        "symbol":        q.get("01. symbol"),
        "open":          _f(q.get("02. open")),
        "high":          _f(q.get("03. high")),
        "low":           _f(q.get("04. low")),
        "price":         _f(q.get("05. price")),
        "volume":        _i(q.get("06. volume")),
        "latest_day":    q.get("07. latest trading day"),
        "prev_close":    _f(q.get("08. previous close")),
        "change":        _f(q.get("09. change")),
        "change_pct":    q.get("10. change percent", "0%").replace("%", ""),
    }


def fetch_daily(symbol: str, api_key: str, outputsize: str = "compact") -> pd.DataFrame:
    """
    Daily OHLCV price history as a DataFrame indexed by date.
    outputsize: 'compact' = last 100 days, 'full' = up to 20 years
    """
    data = _get({
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
    }, api_key)

    ts = data.get("Time Series (Daily)", {})
    if not ts:
        return pd.DataFrame()

    rows = []
    for date_str, vals in ts.items():
        rows.append({
            "date":   pd.to_datetime(date_str),
            "open":   float(vals["1. open"]),
            "high":   float(vals["2. high"]),
            "low":    float(vals["3. low"]),
            "close":  float(vals["4. close"]),
            "volume": int(vals["5. volume"]),
        })

    df = pd.DataFrame(rows).sort_values("date").set_index("date")
    return df


def fetch_overview(symbol: str, api_key: str) -> dict:
    """
    Company fundamentals: P/E, P/S, P/B, EPS, revenue growth, margins, etc.
    Note: Not available for all tickers on the free tier.
    """
    data = _get({"function": "OVERVIEW", "symbol": symbol}, api_key)
    if not data or "Symbol" not in data:
        return {}

    def pct(v):
        try: return float(v)
        except: return None

    def num(v):
        try: return float(v)
        except: return None

    return {
        "name":             data.get("Name"),
        "sector":           data.get("Sector", "N/A"),
        "industry":         data.get("Industry", "N/A"),
        "currency":         data.get("Currency", "USD"),
        "market_cap":       num(data.get("MarketCapitalization")),
        "pe_ratio":         num(data.get("PERatio")),
        "forward_pe":       num(data.get("ForwardPE")),
        "ps_ratio":         num(data.get("PriceToSalesRatioTTM")),
        "pb_ratio":         num(data.get("PriceToBookRatio")),
        "peg_ratio":        num(data.get("PEGRatio")),
        "ev_ebitda":        num(data.get("EVToEBITDA")),
        "eps":              num(data.get("EPS")),
        "revenue_per_share":num(data.get("RevenuePerShareTTM")),
        "profit_margin":    num(data.get("ProfitMargin")),
        "operating_margin": num(data.get("OperatingMarginTTM")),
        "gross_margin":     num(data.get("GrossProfitTTM")),   # gross profit, not margin %
        "roe":              num(data.get("ReturnOnEquityTTM")),
        "roa":              num(data.get("ReturnOnAssetsTTM")),
        "revenue_growth":   num(data.get("QuarterlyRevenueGrowthYOY")),
        "eps_growth":       num(data.get("QuarterlyEarningsGrowthYOY")),
        "debt_equity":      num(data.get("DebtToEquityRatio")),
        "current_ratio":    num(data.get("CurrentRatio")),
        "dividend_yield":   num(data.get("DividendYield")),
        "payout_ratio":     num(data.get("PayoutRatio")),
        "52w_high":         num(data.get("52WeekHigh")),
        "52w_low":          num(data.get("52WeekLow")),
        "50d_ma":           num(data.get("50DayMovingAverage")),
        "200d_ma":          num(data.get("200DayMovingAverage")),
        "beta":             num(data.get("Beta")),
        "analyst_target":   num(data.get("AnalystTargetPrice")),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v):
    try: return float(v)
    except: return None

def _i(v):
    try: return int(v)
    except: return None
