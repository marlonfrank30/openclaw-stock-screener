# Dashboard Template & Scripts Guide

## Interactive HTML Dashboard

When the user asks for a dashboard or screener UI, use this structure as a React/HTML artifact.
Pipe screener JSON output into the artifact data.

### Artifact structure

```jsx
// Get screener data first:
// python3 screener.py --tickers ... --output json > data.json
// Then embed in artifact or fetch dynamically.

// Key UI elements to include:
// 1. Filter controls (RSI range slider, P/E max, sector dropdown)
// 2. Sortable results table with color-coded signals
// 3. Mini sparklines if you have price history (optional)
// 4. Signal badge: green=BULLISH, red=BEARISH, yellow=NEUTRAL
```

### Color coding for signals
- BULLISH → green (#22c55e or Tailwind `text-green-500`)
- BEARISH → red (#ef4444 or `text-red-500`)
- NEUTRAL → amber (#f59e0b or `text-amber-500`)

### RSI color coding
- RSI < 30 → green (oversold, watch for reversal)
- RSI 30–70 → default
- RSI > 70 → red (overbought, caution)

---

## Scripts Usage Reference

### analyze_stock.py

```bash
# Single stock, default 6-month period
python3 scripts/analyze_stock.py --ticker AAPL

# Custom period
python3 scripts/analyze_stock.py --ticker AAPL --period 1y

# Compare multiple stocks
python3 scripts/analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare --period 1y

# JSON output (for piping into artifacts or further processing)
python3 scripts/analyze_stock.py --ticker AAPL --output json
```

**Valid periods:** `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`

---

### screener.py

```bash
# Basic scan, no filters (returns all with ranking)
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL,JPM,V,JNJ

# Use a preset
python3 scripts/screener.py --tickers ... --preset momentum
python3 scripts/screener.py --tickers ... --preset value
python3 scripts/screener.py --tickers ... --preset breakout
python3 scripts/screener.py --tickers ... --preset oversold_reversal

# Custom filters
python3 scripts/screener.py --tickers ... --rsi-min 40 --rsi-max 65 --pe-max 30
python3 scripts/screener.py --tickers ... --volume-spike 1.5 --above-sma50

# JSON output for dashboard
python3 scripts/screener.py --tickers ... --output json
```

---

### indicators.py (library — import, don't run directly)

```python
from scripts.indicators import rsi, macd, bollinger_bands, sma, ema, volume_spike, signal_summary

# All functions accept a pandas Series of closing prices
# signal_summary() returns: {"verdict": "BULLISH/BEARISH/NEUTRAL", "score": float, "signals": [str]}
```

---

## Popular Ticker Lists

Use these when the user says "scan the market" or doesn't specify tickers:

### Mega-cap tech
```
AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA,AVGO,ORCL,ADBE
```

### S&P 500 top 20 (approx)
```
AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AVGO,BRK-B,JPM,LLY,V,UNH,XOM,MA,JNJ,PG,HD,COST,MRK
```

### Mixed sectors
```
AAPL,MSFT,JPM,JNJ,XOM,COST,NEE,CAT,BA,GS
```

### UK stocks (London Stock Exchange — use .L suffix)
```
SHEL.L,AZN.L,HSBA.L,ULVR.L,BP.L,RIO.L,GSK.L,LLOY.L,BARC.L,VOD.L
```

---

## Combining with Web Search

For sentiment analysis (not built into the scripts), instruct Claude to:
1. Run the technical/fundamental analysis via scripts
2. Use web_search tool to fetch recent news for top results
3. Note sentiment alongside technical signals in the report

Example prompt pattern:
> "Analyze NVDA technically, then search for recent news about Nvidia earnings and factor that into the summary."
