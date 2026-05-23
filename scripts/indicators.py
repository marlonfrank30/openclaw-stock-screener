"""
indicators.py — Reusable technical indicator calculations for OpenClaw stock analysis.
All functions accept a pandas Series or DataFrame and return pandas objects.
"""

import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    })


def bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Upper band, middle (SMA), lower band."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return pd.DataFrame({
        "upper": sma + std_dev * std,
        "middle": sma,
        "lower": sma - std_dev * std,
    })


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def volume_spike(volume: pd.Series, period: int = 20) -> pd.Series:
    """Ratio of current volume to rolling average (>1.5 = notable spike)."""
    avg_vol = volume.rolling(period).mean()
    return volume / avg_vol


def signal_summary(close: pd.Series, volume: pd.Series) -> dict:
    """
    Returns a dict with bullish/bearish/neutral signals and a composite score (-3 to +3).
    Positive = bullish, negative = bearish.
    """
    signals = []
    score = 0

    # RSI signal
    r = rsi(close).iloc[-1]
    if r < 35:
        signals.append(f"RSI {r:.1f} — oversold (bullish reversal watch)")
        score += 1
    elif r > 70:
        signals.append(f"RSI {r:.1f} — overbought (bearish caution)")
        score -= 1
    else:
        signals.append(f"RSI {r:.1f} — neutral")

    # MACD signal
    m = macd(close)
    last_hist = m["histogram"].iloc[-1]
    prev_hist = m["histogram"].iloc[-2]
    if last_hist > 0 and prev_hist <= 0:
        signals.append("MACD bullish crossover")
        score += 1
    elif last_hist < 0 and prev_hist >= 0:
        signals.append("MACD bearish crossover")
        score -= 1
    elif last_hist > 0:
        signals.append("MACD above signal — bullish momentum")
        score += 0.5
    else:
        signals.append("MACD below signal — bearish momentum")
        score -= 0.5

    # Price vs SMA50 and SMA200
    s50 = sma(close, 50).iloc[-1]
    s200 = sma(close, 200).iloc[-1]
    price = close.iloc[-1]
    if price > s50 and price > s200:
        signals.append("Price above SMA50 and SMA200 — bullish trend")
        score += 1
    elif price < s50 and price < s200:
        signals.append("Price below SMA50 and SMA200 — bearish trend")
        score -= 1
    else:
        signals.append("Price between SMA50 and SMA200 — mixed trend")

    # Volume spike
    vs = volume_spike(volume).iloc[-1]
    if vs > 1.5 and price > close.iloc[-2]:
        signals.append(f"Volume spike {vs:.1f}x with price rise — accumulation signal")
        score += 0.5
    elif vs > 1.5 and price < close.iloc[-2]:
        signals.append(f"Volume spike {vs:.1f}x with price drop — distribution signal")
        score -= 0.5

    # Overall verdict
    if score >= 1.5:
        verdict = "BULLISH"
    elif score <= -1.5:
        verdict = "BEARISH"
    else:
        verdict = "NEUTRAL"

    return {"verdict": verdict, "score": round(score, 1), "signals": signals}
