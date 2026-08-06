
from __future__ import annotations
import pandas as pd
from pathlib import Path
from data_source import fetch_history
from engine import score_latest
from db import init_db, save_signals, open_trade, get_trades, close_trade, get_signals

BASE = Path(__file__).parent

def _update_open_trades():
    trades = get_trades()
    if trades.empty: return 0
    closed = 0
    for _, t in trades[trades.status=="OPEN"].iterrows():
        try:
            hist = fetch_history(t.symbol, "1mo")
            if hist.empty: continue
            today = hist.iloc[-1]
            # Conservative intraday ambiguity rule: if both stop and target are touched,
            # assume stop was hit first.
            if float(today.Low) <= float(t.stop):
                close_trade(int(t.id), float(t.stop), "Stop loss")
                closed += 1
            elif float(today.High) >= float(t.target2):
                close_trade(int(t.id), float(t.target2), "Target 2")
                closed += 1
            elif float(today.High) >= float(t.target1):
                close_trade(int(t.id), float(t.target1), "Target 1")
                closed += 1
        except Exception:
            pass
    return closed
def _open_previous_buy_signals():
    previous = get_signals(limit=1000, latest_only=False)

    if previous.empty:
        return 0

    dates = sorted(previous["signal_date"].dropna().unique(), reverse=True)

    if len(dates) < 2:
        return 0

    previous_date = dates[1]

    candidates = previous[
        (previous["signal_date"] == previous_date) &
        (previous["signal"] == "BUY")
    ].sort_values("score", ascending=False)

    opened = 0

    for _, r in candidates.head(5).iterrows():
        try:
            hist = fetch_history(r["symbol"], "1mo")

            if hist.empty:
                continue

            latest_date = pd.Timestamp(hist.index[-1]).date().isoformat()

            # Open only when a newer trading session exists
            if latest_date > previous_date:
                trade = r.to_dict()
                trade["price"] = float(hist.iloc[-1]["Open"])
                opened += int(open_trade(trade))

        except Exception as e:
            print(f"Entry error {r['symbol']}: {e}")

    return opened
def run_daily_scan(auto_open=True):
    init_db()
    _update_open_trades()
    universe = pd.read_csv(BASE / "tickers.csv")
    rows = []

    for _, x in universe.iterrows():
        try:
            scored = score_latest(fetch_history(x.symbol, "2y"))
            if scored:
                scored.update(symbol=x.symbol, name=x["name"])
                rows.append(scored)
        except Exception as e:
            print(f"{x.symbol}: {e}")

    save_signals(rows)

    buy_rows = [r for r in rows if r["signal"] == "BUY"]

    opened = 0
    if auto_open:
        opened = _open_previous_buy_signals()

    return {
        "scanned": len(rows),
        "buy_count": len(buy_rows),
        "opened": opened
    }


if __name__ == "__main__":
    print(run_daily_scan(auto_open=True))
