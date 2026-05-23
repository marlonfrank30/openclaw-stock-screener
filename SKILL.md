---
name: openclaw-stock-analysis
description: >
  Stock market scanning, screening, and analysis skill for OpenClaw. Use this skill whenever
  the user wants to analyze stocks, scan the market for opportunities, screen shares by
  criteria (volume, momentum, breakouts), run technical analysis (RSI, MACD, moving averages),
  review fundamentals (P/E ratio, P/S ratio, P/B ratio, PEG, EV/EBITDA, revenue, earnings),
  generate stock research reports, or build stock dashboards and screeners. Trigger this skill
  for any request involving share prices, stock tickers, market screening, portfolio analysis,
  or investment research — even if phrased casually like "find me some good stocks" or
  "how is AAPL looking". Data is fetched via the Alpha Vantage API — ensure ALPHA_VANTAGE_KEY
  is set in the environment before running any scripts.
---

# OpenClaw Stock Analysis Skill

Scans, screens, and analyses stocks using the **Alpha Vantage API** (`av_client.py`).
Yahoo Finance is not used — it blocks server and datacenter IPs. Alpha Vantage works
reliably from any environment including servers, k8s clusters, and VMs.

Produces output in the right format for context: interactive dashboards for exploration,
structured reports for research, and quick summaries for conversational queries.

---

## Dependencies

```bash
pip install requests pandas numpy
```

**API key required:**
```bash
export ALPHA_VANTAGE_KEY="your_key_here"
# Free key: https://www.alphavantage.co/support/#api-key
```

> **Free tier limits:** 25 requests/day, ~5 requests/minute.
> Each ticker uses 2 API calls (quote + fundamentals) → ~12 tickers/day on free tier.

---

## Data Source — Alpha Vantage

All market data is fetched via `scripts/av_client.py` which wraps three Alpha Vantage endpoints:

| Function | Endpoint | Data returned |
|---|---|---|
| `fetch_quote()` | `GLOBAL_QUOTE` | Current price, volume, day change |
| `fetch_daily()` | `TIME_SERIES_DAILY` | OHLCV price history (used for technical indicators) |
| `fetch_overview()` | `OVERVIEW` | All fundamentals: P/E, P/S, P/B, PEG, EV/EBITDA, margins, ROE, growth, etc. |

---

## Output Format Decision Tree

| User intent | Output format |
|---|---|
| "Analyze AAPL" / single stock deep-dive | Structured markdown report + key metrics table |
| "Scan for breakout stocks" / screening | Interactive HTML artifact with sortable table |
| "Quick summary of TSLA" / casual ask | Short in-chat summary (3–5 bullet points) |
| "Build me a dashboard" / explicit request | Full interactive HTML artifact |
| "Generate a report on..." | Markdown report (offer PDF if asked) |

When unsure, default to a **structured markdown report** — it's readable inline and copyable.

---

## Core Workflows

### 1. Single Stock Analysis

Use `scripts/analyze_stock.py`. Produces:
- Price summary (current, 52-week high/low, % change, analyst target, beta)
- Valuation ratios: P/E, Forward P/E, P/S, P/B, PEG, EV/EBITDA
- Profitability: Net margin, Operating margin, ROE, ROA
- Growth: Revenue growth YoY, EPS growth YoY
- Financial health: Debt/Equity, Current ratio
- Dividends: Yield, Payout ratio
- Technical indicators: RSI(14), MACD, SMA(20/50/200), Bollinger Bands, Volume spike
- Signal summary: BULLISH / BEARISH / NEUTRAL with score and reasoning

```bash
python3 scripts/analyze_stock.py --ticker NVDA
python3 scripts/analyze_stock.py --ticker NVDA --period full   # full price history
python3 scripts/analyze_stock.py --ticker NVDA --output json   # JSON for dashboards
```

### 2. Market Screener

Use `scripts/screener.py`. Screens a watchlist against configurable fundamental and technical filters.

```bash
# Use a preset
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL --preset momentum

# Custom filters
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA \
  --pe-max 30 --ps-max 5 --roe-min 0.15 --rsi-min 45 --rsi-max 70
```

### 3. Comparative Analysis

Compare 2–5 stocks side by side:

```bash
python3 scripts/analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare
```

### 4. Interactive Dashboard (HTML Artifact)

After running a screener or analysis with `--output json`, pipe the data into an HTML artifact.
See `references/scripts_guide.md` for the dashboard template and color-coding guidance.

---

## Technical Indicators — Reference

### RSI (Relative Strength Index)
- **Formula**: `RSI = 100 - (100 / (1 + RS))` where RS = avg gain / avg loss over 14 periods
- **Signals**: >70 overbought, <30 oversold, 40–60 neutral trend
- **Use case**: Identify entry/exit points and divergence

### MACD (Moving Average Convergence Divergence)
- **Components**: MACD line (12 EMA − 26 EMA), Signal line (9 EMA of MACD), Histogram
- **Signals**: Bullish crossover when MACD crosses above signal; bearish when below
- **Use case**: Trend direction and momentum

### Moving Averages
- **SMA20**: Short-term trend; price above = bullish short-term
- **SMA50**: Medium-term trend; golden cross (50 > 200) = bullish
- **SMA200**: Long-term trend; "golden cross" and "death cross" signals

### Bollinger Bands
- **Formula**: SMA20 ± (2 × std dev of 20-period close)
- **Signals**: Price touching upper band = overbought; lower band = oversold
- **Use case**: Volatility and breakout detection

### Volume Signals
- Volume spike (>1.5× 20-day avg) with price rise = accumulation (bullish)
- Volume spike with price drop = distribution (bearish)
- Low volume breakout = weak signal; high volume breakout = strong

---

## Fundamental Metrics — Reference

| Metric | Good range (general) | Notes |
|---|---|---|
| P/E Ratio | 10–25 (value), 25–50 (growth) | Compare to sector average |
| P/S Ratio | <1 cheap, 1–3 fair, >8 expensive | Useful for pre-profit growth companies |
| P/B Ratio | <1 below book, 1–3 fair, >8 premium | Compare within sector |
| PEG Ratio | <1 undervalued vs growth, 1–2 fair | Adjusts P/E for growth rate |
| EV/EBITDA | <10 cheap, 10–20 fair, >20 expensive | Better than P/E for leveraged companies |
| ROE | >15% strong | Higher = better capital efficiency |
| Revenue Growth | >10% YoY | Consistency matters |
| Debt/Equity | <1.0 | <0.5 preferred |
| Dividend Yield | 2–5% | Context-dependent |

Always compare fundamentals to **sector peers**, not absolute thresholds.

---

## Screener Presets

| Preset | What it finds |
|---|---|
| `momentum` | RSI 50–70, above SMA50 & SMA200, bullish MACD, volume spike ≥1.3× |
| `value` | P/E ≤20, P/S ≤3, P/B ≤3, PEG ≤1.5, D/E ≤1, ROE ≥10% |
| `growth` | Revenue & EPS growth ≥15% |
| `quality` | ROE ≥15%, ROA ≥8%, profit margin ≥10%, current ratio ≥1.5 |
| `dividend` | Yield 2–10%, profit margin ≥8%, D/E ≤1.5 |
| `breakout` | Within 2% of 52W high, volume ≥2×, RSI 55–75 |
| `oversold_reversal` | RSI <35, near lower Bollinger Band |

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/av_client.py` | Alpha Vantage API client — all data fetching lives here |
| `scripts/analyze_stock.py` | Single/multi-stock deep analysis |
| `scripts/screener.py` | Batch screening with configurable filters and presets |
| `scripts/indicators.py` | Pure math: RSI, MACD, Bollinger Bands, SMA, volume spike, signal scoring |

Read `references/scripts_guide.md` for full argument reference and ticker lists.

---

## Error Handling

- **Rate limits**: Alpha Vantage free tier allows ~5 requests/minute. Scripts add `time.sleep(0.8)` between calls automatically. If you hit a rate limit, wait 60 seconds and retry.
- **Missing fundamentals**: Some tickers (ETFs, small caps, non-US stocks) may not have full overview data from Alpha Vantage. The scripts gracefully return `N/A` for missing fields.
- **Invalid ticker**: An empty response from `fetch_quote()` means the ticker is invalid or delisted. The script will print an error and skip it.
- **Key not set**: If `ALPHA_VANTAGE_KEY` is not set, scripts will raise a clear `EnvironmentError` with instructions.
- **Market hours**: Prices reflect the latest trading day close. Note this when reporting to users.

---

## Response Quality Guidelines

1. **Always state the data date** — every report includes the latest trading day from Alpha Vantage
2. **Never give buy/sell advice** — present signals and let the user decide; add disclaimer for reports
3. **Contextualize signals** — a RSI of 68 means different things in a bull vs bear market
4. **Flag limitations** — e.g. "This screener covers only the tickers you provided, not the full market"
5. **Note free tier constraints** — if the user wants to screen many tickers, flag the 25 req/day limit
6. **Offer next steps** — after a scan, suggest: deep-dive on top results, compare to sector, set alerts
