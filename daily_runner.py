from __future__ import annotations

import pandas as pd
from pathlib import Path

from data_source import fetch_history
from engine import score_latest
from db import (
    init_db,
    save_signals,
    open_trade,
    get_trades,
    close_trade,
    get_signals,
)

BASE = Path(__file__).parent


def _update_open_trades():
    trades = get_trades()

    if trades.empty:
        return 0

    closed = 0

    open_trades = trades[trades["status"] == "OPEN"]

    for _, t in open_trades.iterrows():
        try:
            hist = fetch_history(t["symbol"], "1mo")

            if hist.empty:
                continue

            today = hist.iloc[-1]

            low = float(today["Low"])
            high = float(today["High"])

            stop = float(t["stop"])
            target1 = float(t["target1"])
            target2 = float(t["target2"])

            # Conservative intraday ambiguity rule:
            # If stop and target are both touched
            # during the same candle, assume stop
            # was hit first.
            if low <= stop:
                close_trade(
                    int(t["id"]),
                    stop,
                    "Stop loss",
                )
                closed += 1

            elif high >= target2:
                close_trade(
                    int(t["id"]),
                    target2,
                    "Target 2",
                )
                closed += 1

            elif high >= target1:
                close_trade(
                    int(t["id"]),
                    target1,
                    "Target 1",
                )
                closed += 1

        except Exception as e:
            print(
                f"Trade update error "
                f"{t['symbol']}: {e}"
            )

    return closed


def _open_previous_buy_signals():
    previous = get_signals(
        limit=1000,
        latest_only=False,
    )

    if previous.empty:
        return 0

    # Make sure signal_date is treated consistently.
    previous = previous.copy()

    previous["signal_date"] = pd.to_datetime(
        previous["signal_date"]
    ).dt.date

    dates = sorted(
        previous["signal_date"]
        .dropna()
        .unique(),
        reverse=True,
    )

    # We need at least two different
    # signal dates:
    #
    # dates[0] = latest scan
    # dates[1] = previous scan
    if len(dates) < 2:
        return 0

    previous_date = dates[1]

    candidates = previous[
        (previous["signal_date"] == previous_date)
        & (previous["signal"] == "BUY")
    ].sort_values(
        "score",
        ascending=False,
    )

    opened = 0

    # Maximum 5 new paper trades
    # from the previous BUY signals.
    for _, r in candidates.head(5).iterrows():
        try:
            symbol = r["symbol"]

            hist = fetch_history(
                symbol,
                "1mo",
            )

            if hist.empty:
                continue

            hist = hist.copy()

            # Convert history index to dates.
            history_dates = pd.to_datetime(
                hist.index
            ).date

            # Find ALL sessions after
            # the original BUY signal date.
            newer_mask = (
                history_dates > previous_date
            )

            new_sessions = hist.loc[
                newer_mask
            ]

            if new_sessions.empty:
                # No newer trading session yet.
                continue

            # IMPORTANT:
            # Take the FIRST trading session
            # after the BUY signal.
            entry_row = new_sessions.iloc[0]

            entry_date = pd.Timestamp(
                new_sessions.index[0]
            ).date()

            entry_price = float(
                entry_row["Open"]
            )

            trade = r.to_dict()

            # Keep original BUY signal date.
            # This helps prevent the same signal
            # from being reused.
            trade["signal_date"] = (
                previous_date.isoformat()
            )

            # Paper trade enters at the OPEN
            # of the first trading session
            # after the BUY signal.
            trade["price"] = entry_price

            # Store entry date too if open_trade()
            # supports additional dictionary fields.
            trade["entry_date"] = (
                entry_date.isoformat()
            )

            result = open_trade(trade)

            opened += int(result)

            if result:
                print(
                    f"OPENED {symbol} | "
                    f"Signal: {previous_date} | "
                    f"Entry: {entry_date} | "
                    f"Price: {entry_price:.2f}"
                )

        except Exception as e:
            print(
                f"Entry error "
                f"{r['symbol']}: {e}"
            )

    return opened


def run_daily_scan(auto_open=True):
    init_db()

    # ---------------------------------
    # 1. Update existing open trades
    # ---------------------------------
    closed = _update_open_trades()

    # ---------------------------------
    # 2. Load Saudi stock universe
    # ---------------------------------
    universe = pd.read_csv(
        BASE / "tickers.csv"
    )

    rows = []

    # ---------------------------------
    # 3. Scan all stocks
    # ---------------------------------
    for _, x in universe.iterrows():
        try:
            hist = fetch_history(
                x["symbol"],
                "2y",
            )

            scored = score_latest(hist)

            if scored:
                scored.update(
                    symbol=x["symbol"],
                    name=x["name"],
                )

                rows.append(scored)

        except Exception as e:
            print(
                f"{x['symbol']}: {e}"
            )

    # ---------------------------------
    # 4. Save today's signals
    # ---------------------------------
    save_signals(rows)

    # ---------------------------------
    # 5. Count today's BUY signals
    # ---------------------------------
    buy_rows = [
        r
        for r in rows
        if r["signal"] == "BUY"
    ]

    # ---------------------------------
    # 6. Open previous BUY signals
    #    using the next session OPEN
    # ---------------------------------
    opened = 0

    if auto_open:
        opened = (
            _open_previous_buy_signals()
        )

    # ---------------------------------
    # 7. Return scan summary
    # ---------------------------------
    return {
        "scanned": len(rows),
        "buy_count": len(buy_rows),
        "opened": opened,
        "closed": closed,
    }


if __name__ == "__main__":
    result = run_daily_scan(
        auto_open=True
    )

    print(result)
