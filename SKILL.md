---
name: openclaw-stock-analysis
description: >
  Stock market scanning, screening, and analysis skill for OpenClaw. Use this skill whenever
  the user wants to analyze stocks, scan the market for opportunities, screen shares by
  criteria (volume, momentum, breakouts), run technical analysis (RSI, MACD, moving averages),
  review fundamentals (P/E ratio, revenue, earnings), generate stock research reports, or
  build stock dashboards and screeners. Trigger this skill for any request involving share
  prices, stock tickers, market screening, portfolio analysis, or investment research —
  even if phrased casually like "find me some good stocks" or "how is AAPL looking".
---

# OpenClaw Stock Analysis Skill

Helps Claude scan, screen, and analyze stocks using Yahoo Finance (`yfinance`). Produces
output in the right format for context: interactive dashboards for exploration, structured
reports for research, and quick summaries for conversational queries.

---

## Dependencies

```bash
pip install yfinance pandas numpy
```

All three are required. Always install silently (`-q`) and verify before running analysis scripts.

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
- Price summary (current, 52-week high/low, % change)
- Technical indicators: RSI(14), MACD, SMA(20/50/200), Bollinger Bands
- Fundamentals: P/E, EPS, revenue, market cap, dividend yield
- Volume analysis: average vs current, unusual activity flag
- Signal summary: bullish / bearish / neutral with reasoning

```bash
python3 scripts/analyze_stock.py --ticker AAPL --period 6mo
```

### 2. Market Screener

Use `scripts/screener.py`. Screens a watchlist or index against configurable criteria.

```bash
# Screen S&P 500-like list for momentum + value
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL \
  --rsi-min 40 --rsi-max 65 --pe-max 30 --volume-spike 1.5
```

Outputs a ranked table. Feed this into an HTML artifact for interactivity.

### 3. Comparative Analysis

Compare 2–5 stocks side by side:

```bash
python3 scripts/analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare --period 1y
```

### 4. Interactive Dashboard (HTML Artifact)

After running a screener or analysis, build an HTML artifact using the data.
See `references/dashboard_template.md` for the full template and guidance.

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
| EPS Growth | >10% YoY | Accelerating = bullish |
| Revenue Growth | >10% YoY | Consistency matters |
| Debt/Equity | <1.0 | <0.5 preferred |
| Return on Equity | >15% | Higher = better capital efficiency |
| Dividend Yield | 2–5% | Context-dependent |
| Market Cap | — | Affects volatility expectations |

Always compare fundamentals to **sector peers**, not absolute thresholds.

---

## Screener Criteria — Common Presets

Use these as starting points; adapt to user's goals.

**Momentum Play**
- RSI: 50–70 (trending up, not overbought)
- Price > SMA50 and SMA200
- Volume spike > 1.3× average
- MACD bullish crossover in last 5 days

**Value Hunt**
- P/E < 20 (or below sector average)
- EPS growth > 10% YoY
- Price near 52-week low (within 20%)
- Debt/Equity < 0.5

**Breakout Scanner**
- Price within 2% of 52-week high
- Volume > 2× 20-day average
- RSI 55–75 (momentum building)
- Price crossed above SMA50 in last 10 days

**Oversold Reversal**
- RSI < 35
- Price near lower Bollinger Band
- Positive EPS / fundamentally sound
- No recent bad news (combine with web search)

---

## Scripts

See `scripts/` directory for:
- `analyze_stock.py` — Single/multi-stock analysis
- `screener.py` — Batch screening with configurable filters
- `indicators.py` — Reusable indicator calculation functions

Read `references/scripts_guide.md` for full usage and argument reference.

---

## Error Handling

- **Rate limits**: `yfinance` is free but rate-limited. Add `time.sleep(0.5)` between tickers when screening large lists.
- **Missing data**: Some tickers lack fundamentals (ETFs, small caps). Gracefully skip and note in output.
- **Delisted stocks**: Wrap `yf.Ticker().history()` in try/except; empty DataFrame = likely delisted.
- **Market hours**: After-hours prices may differ from last close. Note this in output when relevant.

---

## Response Quality Guidelines

1. **Always state the data date** — note when data was last fetched (yfinance timestamps are available)
2. **Never give buy/sell advice** — present signals and let the user decide; add disclaimer for reports
3. **Contextualize signals** — a RSI of 68 means different things in a bull vs bear market
4. **Flag limitations** — e.g. "This screener covers only the tickers you provided, not the full market"
5. **Offer next steps** — after a scan, suggest: deep-dive on top results, set alerts, compare to sector
