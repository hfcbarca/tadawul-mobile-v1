from __future__ import annotations
import numpy as np
import pandas as pd


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().dropna(subset=["Close"]).sort_index()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"].fillna(0)

    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))

    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    df["MACD"] = macd
    df["MACD_SIGNAL"] = signal
    df["MACD_HIST"] = macd - signal

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.rolling(14).mean()

    df["VOL20"] = vol.rolling(20).mean()
    df["AVG_VALUE20"] = df["VOL20"] * close
    df["RVOL"] = vol / df["VOL20"].replace(0, np.nan)
    df["HIGH20_PREV"] = high.shift(1).rolling(20).max()
    df["LOW20_PREV"] = low.shift(1).rolling(20).min()
    df["HIGH52W"] = high.rolling(252).max()
    df["RET20"] = close.pct_change(20)
    return df


def score_latest(df: pd.DataFrame) -> dict | None:
    d = add_indicators(df)
    if len(d) < 205:
        return None
    r = d.iloc[-1]
    p = d.iloc[-2]
    required = ["Close", "SMA50", "SMA200", "RSI14", "MACD", "MACD_SIGNAL", "ATR14", "RVOL"]
    if any(pd.isna(r[x]) for x in required):
        return None

    score = 0.0
    reasons = []

    # Trend: 30 points
    if r.Close > r.SMA50:
        score += 12; reasons.append("Price above SMA50")
    if r.SMA50 > r.SMA200:
        score += 12; reasons.append("SMA50 above SMA200")
    if r.SMA50 > p.SMA50:
        score += 6; reasons.append("SMA50 rising")

    # Momentum: 20 points
    if 50 <= r.RSI14 <= 68:
        score += 10; reasons.append("RSI in constructive zone")
    elif 45 <= r.RSI14 < 50 or 68 < r.RSI14 <= 72:
        score += 5
    if r.MACD > r.MACD_SIGNAL:
        score += 7; reasons.append("MACD bullish")
    if r.MACD_HIST > p.MACD_HIST:
        score += 3; reasons.append("MACD momentum improving")

    # Volume: 15 points
    if r.RVOL >= 1.5:
        score += 15; reasons.append(f"Strong volume ({r.RVOL:.1f}x)")
    elif r.RVOL >= 1.15:
        score += 10; reasons.append(f"Above-average volume ({r.RVOL:.1f}x)")
    elif r.RVOL >= 0.9:
        score += 5

    # Breakout / structure: 20 points
    if pd.notna(r.HIGH20_PREV) and r.Close > r.HIGH20_PREV:
        score += 15; reasons.append("20-day breakout")
    elif pd.notna(r.HIGH20_PREV) and r.Close >= 0.98 * r.HIGH20_PREV:
        score += 9; reasons.append("Near 20-day breakout")
    if pd.notna(r.HIGH52W) and r.Close >= 0.90 * r.HIGH52W:
        score += 5; reasons.append("Near 52-week high")

    # Risk / recent return quality: 15 points
    atr_pct = float(r.ATR14 / r.Close) if r.Close else np.nan
    if np.isfinite(atr_pct):
        if 0.012 <= atr_pct <= 0.04:
            score += 8
        elif atr_pct < 0.06:
            score += 4
    if pd.notna(r.RET20):
        if 0.02 <= r.RET20 <= 0.15:
            score += 7; reasons.append("Positive 20-day momentum")
        elif 0 < r.RET20 < 0.20:
            score += 3

    score = min(round(score, 1), 100)
    close = float(r.Close)
    atr = float(r.ATR14)
    support = float(r.LOW20_PREV) if pd.notna(r.LOW20_PREV) else close - 2*atr
    stop = max(support * 0.995, close - 2.0 * atr)
    if stop >= close:
        stop = close - 1.5 * atr
    risk = max(close - stop, 0.01)
    target1 = close + 2.0 * risk
    target2 = close + 3.0 * risk

    if score >= 80 and r.AVG_VALUE20 >= 5_000_000:
        signal = "BUY"
    elif score >= 65:
        signal = "WATCH"
    elif score < 40:
        signal = "AVOID"
    else:
        signal = "NEUTRAL"

    return {
        "date": pd.Timestamp(d.index[-1]).date().isoformat(),
        "price": round(close, 2),
        "score": score,
        "signal": signal,
        "entry_low": round(close - 0.25*atr, 2),
        "entry_high": round(close + 0.10*atr, 2),
        "stop": round(stop, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "rsi": round(float(r.RSI14), 1),
        "rvol": round(float(r.RVOL), 2),
        "atr_pct": round(100*atr_pct, 2) if np.isfinite(atr_pct) else None,
        "reasons": "; ".join(reasons[:8]),
    }
