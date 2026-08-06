from __future__ import annotations
import pandas as pd
import yfinance as yf


def fetch_history(symbol: str, period: str = "2y") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False, threads=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance may return (Price, Ticker) columns.
        df.columns = df.columns.get_level_values(0)
    cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]
    return df[cols].copy()
