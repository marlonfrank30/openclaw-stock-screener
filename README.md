# 📈 OpenClaw Stock Screener

An agentic stock analysis and screening toolkit powered by [Yahoo Finance](https://finance.yahoo.com/). Scan, filter, and deep-analyse shares using a full suite of technical and fundamental indicators — built as a skill for the [OpenClaw](https://github.com/marlonfrank30) AI agent framework.

---

## 🗂 File Structure

```
openclaw-stock-screener/
├── SKILL.md                  # OpenClaw skill definition
├── README.md                 # This file
├── scripts/
│   ├── indicators.py         # RSI, MACD, Bollinger Bands, SMA, signal scoring
│   ├── analyze_stock.py      # Single or multi-stock deep analysis
│   └── screener.py           # Batch screener with fundamental + technical filters
└── references/
    └── scripts_guide.md      # Full argument reference and ticker lists
```
---

## 📦 File Summary

| File | Purpose |
|---|---|
| `SKILL.md` | The skill definition — drop this into your OpenClaw skills folder |
| `scripts/indicators.py` | Reusable library: RSI, MACD, Bollinger Bands, volume spike, signal scoring |
| `scripts/analyze_stock.py` | Single or multi-stock deep analysis with technical + fundamental output |
| `scripts/screener.py` | Batch screener with presets (momentum, value, breakout, oversold reversal) |
| `references/scripts_guide.md` | Usage reference, popular ticker lists, dashboard guidance |

## 📦 Getting Started

1. Place `SKILL.md` in your OpenClaw skills directory
2. Put the `scripts/` folder alongside it
3. Run `pip install yfinance pandas numpy` in your environment
4. Test with: `python3 scripts/analyze_stock.py --ticker AAPL`


---

## ⚙️ Installation
**Requirements:** Python 3.10+

### 1. Clone the repo

```bash
git clone https://github.com/marlonfrank30/openclaw-stock-screener.git
cd openclaw-stock-screener
```

### 2. Create and activate a virtual environment

Modern Linux distributions (Debian, Ubuntu) manage Python system-wide and block direct `pip install`. Use a virtual environment instead:

```bash
# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```
Your terminal prompt will change to show `(venv)` when it's active.

### 3. Install dependencies

```bash
pip install yfinance pandas numpy
```

Verify everything installed correctly:

```bash
python3 -c "import yfinance, pandas, numpy; print('All packages OK')"
```

### 4. Re-activating in future sessions

The virtual environment only stays active for the current terminal session. Every time you open a new terminal, reactivate it before running any scripts:

```bash
cd ~/openclaw-stock-screener
source venv/bin/activate
```

> **Note:** The `venv/` folder is already in `.gitignore` and will not be pushed to GitHub.

---
### 4. OpenClaw Files and Directories
File Purpose
SKILL.md - The skill definition — drop this into your OpenClaw skills folderscripts/indicators.pyReusable library: RSI, MACD, Bollinger Bands, volume spike, signal scoringscripts/analyze_stock.pySingle or multi-stock deep analysis with technical + fundamental outputscripts/screener.pyBatch screener with presets (momentum, value, breakout, oversold reversal)references/scripts_guide.mdUsage reference, popular ticker lists, dashboard guidance
To get started:

Place SKILL.md in your OpenClaw skills directory
Put the scripts/ folder alongside it
Run pip install yfinance pandas numpy in your environment
Test with: python3 scripts/analyze_stock.py --ticker AAPL


## 🔍 analyze_stock.py — Deep Stock Analysis

Produces a full report for one or more stocks covering valuation, profitability, growth, financial health, dividends, and technical signals.

### Basic usage

```bash
python3 scripts/analyze_stock.py --ticker AAPL
```

### Custom time period

```bash
python3 scripts/analyze_stock.py --ticker TSLA --period 1y
```

Valid periods: `1mo` `3mo` `6mo` `1y` `2y` `5y`

### Compare multiple stocks side by side

```bash
python3 scripts/analyze_stock.py --ticker AAPL,MSFT,GOOGL --mode compare --period 1y
```

### JSON output (for piping into dashboards or further processing)

```bash
python3 scripts/analyze_stock.py --ticker NVDA --output json
```

### What the report covers

| Section | Metrics |
|---|---|
| **Price Summary** | Current price, day change, 52W high/low, market cap |
| **Valuation** | P/E, Forward P/E, P/S, P/B, PEG, EV/EBITDA, Price/FCF |
| **Profitability** | Net margin, Gross margin, Operating margin, ROE, ROA |
| **Growth** | Revenue growth, EPS growth, Earnings growth (YoY) |
| **Financial Health** | Debt/Equity, Current ratio, Quick ratio, Free cash flow |
| **Dividends** | Yield, Payout ratio |
| **Technical** | RSI(14), MACD, SMA 20/50/200, Bollinger Bands, Volume spike |
| **Signal** | Composite BULLISH / NEUTRAL / BEARISH verdict with score |

---

## 📊 screener.py — Batch Stock Screener

Screen a list of tickers against any combination of fundamental and technical filters. Results are ranked by composite signal score.

### Basic scan (no filters — ranks all tickers)

```bash
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL
```

### Use a built-in preset

```bash
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL,JPM,V,JNJ --preset value
```

Available presets:

| Preset | What it finds |
|---|---|
| `momentum` | Trending stocks — RSI 50–70, above SMA50 & SMA200, bullish MACD, volume spike |
| `value` | Undervalued stocks — P/E ≤ 20, P/S ≤ 3, P/B ≤ 3, PEG ≤ 1.5, D/E ≤ 1, ROE ≥ 10% |
| `growth` | High-growth — revenue & EPS growth ≥ 15%, gross margin ≥ 30% |
| `quality` | Financially sound — ROE ≥ 15%, ROA ≥ 8%, profit margin ≥ 10%, current ratio ≥ 1.5 |
| `dividend` | Income stocks — yield 2–10%, profit margin ≥ 8%, D/E ≤ 1.5 |
| `breakout` | Near 52W highs — within 2% of high, volume 2×, RSI 55–75 |
| `oversold_reversal` | Bounce candidates — RSI < 35, near lower Bollinger Band |

### Custom filters

Mix and match any filters you need:

```bash
# Value + quality hybrid
python3 scripts/screener.py \
  --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL,JPM,V,JNJ,PG,HD \
  --pe-max 25 \
  --ps-max 5 \
  --roe-min 0.15 \
  --debt-equity-max 1.0

# Growth with technical confirmation
python3 scripts/screener.py \
  --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META \
  --revenue-growth-min 0.20 \
  --gross-margin-min 0.40 \
  --above-sma50 \
  --rsi-min 45 --rsi-max 70

# High dividend yield with healthy fundamentals
python3 scripts/screener.py \
  --tickers JNJ,PG,KO,MRK,VZ,T,XOM,CVX,IBM,MO \
  --dividend-yield-min 0.03 \
  --profit-margin-min 0.10 \
  --debt-equity-max 2.0

# Oversold large-caps (potential reversal plays)
python3 scripts/screener.py \
  --tickers AAPL,MSFT,NVDA,TSLA,AMZN,META,GOOGL,JPM,V,JNJ \
  --rsi-max 35 \
  --pe-max 30
```

### JSON output

```bash
python3 scripts/screener.py --tickers AAPL,MSFT,NVDA --preset momentum --output json
```

### All available filters

**Valuation**
| Flag | Description |
|---|---|
| `--pe-max` | Max trailing P/E ratio |
| `--pe-min` | Min trailing P/E ratio |
| `--ps-max` | Max Price-to-Sales ratio |
| `--pb-max` | Max Price-to-Book ratio |
| `--peg-max` | Max PEG ratio |
| `--ev-ebitda-max` | Max EV/EBITDA |
| `--price-fcf-max` | Max Price-to-Free-Cash-Flow |

**Profitability**
| Flag | Description |
|---|---|
| `--profit-margin-min` | Min net profit margin (e.g. `0.10` = 10%) |
| `--gross-margin-min` | Min gross margin |
| `--roe-min` | Min Return on Equity |
| `--roa-min` | Min Return on Assets |

**Growth**
| Flag | Description |
|---|---|
| `--revenue-growth-min` | Min revenue growth YoY |
| `--eps-growth-min` | Min EPS growth YoY |
| `--earnings-growth-min` | Min earnings growth YoY |

**Financial Health**
| Flag | Description |
|---|---|
| `--debt-equity-max` | Max Debt/Equity ratio |
| `--current-ratio-min` | Min current ratio |
| `--quick-ratio-min` | Min quick ratio |

**Dividends**
| Flag | Description |
|---|---|
| `--dividend-yield-min` | Min dividend yield (e.g. `0.02` = 2%) |
| `--dividend-yield-max` | Max dividend yield |

**Technical**
| Flag | Description |
|---|---|
| `--rsi-min` | Min RSI (14-period) |
| `--rsi-max` | Max RSI |
| `--volume-spike` | Min volume spike ratio (e.g. `1.5` = 1.5× avg) |
| `--above-sma50` | Price must be above 50-day SMA |
| `--above-sma200` | Price must be above 200-day SMA |

---

## 📐 indicators.py — Technical Indicator Library

Used internally by `analyze_stock.py` and `screener.py`. Import directly for custom scripts:

```python
from scripts.indicators import rsi, macd, bollinger_bands, sma, volume_spike, signal_summary
import yfinance as yf

ticker = yf.Ticker("AAPL")
hist = ticker.history(period="6mo")
close = hist["Close"]
volume = hist["Volume"]

print(rsi(close).iloc[-1])           # RSI value
print(macd(close))                   # DataFrame: macd, signal, histogram
print(bollinger_bands(close))        # DataFrame: upper, middle, lower
print(signal_summary(close, volume)) # {"verdict": "BULLISH", "score": 2.0, "signals": [...]}
```

---

## 💡 Popular Ticker Lists

Paste these directly into `--tickers`:

**Mega-cap tech**
```
AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA,AVGO,ORCL,ADBE
```

**S&P 500 top 20**
```
AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AVGO,BRK-B,JPM,LLY,V,UNH,XOM,MA,JNJ,PG,HD,COST,MRK
```

**Dividend income**
```
JNJ,PG,KO,MRK,VZ,T,XOM,CVX,IBM,MO,MMM,ABT,PFE,WMT,CL
```

**UK stocks (London Stock Exchange)**
```
SHEL.L,AZN.L,HSBA.L,ULVR.L,BP.L,RIO.L,GSK.L,LLOY.L,BARC.L,VOD.L
```

---

## ⚠️ Disclaimer

This tool is for **informational and educational purposes only**. Nothing in this repository constitutes financial advice. Always do your own research before making any investment decisions.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

MIT
