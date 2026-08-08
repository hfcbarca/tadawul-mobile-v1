from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from engine import add_indicators, score_latest
from data_source import fetch_history
from db import (
    init_db,
    save_signals,
    get_signals,
    get_trades,
    get_performance,
    STRATEGY_VERSION,
)
from daily_runner import run_daily_scan


st.set_page_config(
    page_title="Tadawul V1",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()
BASE = Path(__file__).parent


st.markdown(
    """
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 4rem;
    max-width: 1250px;
}

[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,.22);
    padding: 12px;
    border-radius: 14px;
}

.signal-card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 16px;
    padding: 15px;
    margin-bottom: 12px;
}

.buy {
    border-left: 6px solid #19a15f;
}

.watch {
    border-left: 6px solid #e0a100;
}

.avoid {
    border-left: 6px solid #d64545;
}

.small {
    opacity: .75;
    font-size: .88rem;
}

@media (max-width: 700px) {
    .block-container {
        padding-left: .8rem;
        padding-right: .8rem;
    }

    h1 {
        font-size: 1.7rem !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


def calculate_performance_from_trades(trade_df):
    if trade_df.empty:
        return {
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_return": 0.0,
            "profit_factor": None,
        }

    closed = trade_df[trade_df.status == "CLOSED"].copy()

    if closed.empty:
        return {
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_return": 0.0,
            "profit_factor": None,
        }

    closed["pnl_pct"] = pd.to_numeric(
        closed["pnl_pct"],
        errors="coerce",
    )

    closed = closed.dropna(subset=["pnl_pct"])

    if closed.empty:
        return {
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_return": 0.0,
            "profit_factor": None,
        }

    wins = closed[closed.pnl_pct > 0]
    losses = closed[closed.pnl_pct <= 0]

    gross_profit = wins.pnl_pct.sum()
    gross_loss = abs(losses.pnl_pct.sum())

    return {
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (
            100 * len(wins) / len(closed)
            if len(closed) > 0
            else 0.0
        ),
        "avg_pnl": float(closed.pnl_pct.mean()),
        "total_return": float(
            ((1 + closed.pnl_pct / 100).prod() - 1) * 100
        ),
        "profit_factor": (
            float(gross_profit / gross_loss)
            if gross_loss > 0
            else None
        ),
    }


st.title("📈 Tadawul V1")

st.caption(
    "30-Day Paper Test • Saudi market decision-support tool • "
    "No real-money execution"
)


universe = pd.read_csv(BASE / "tickers.csv")


top_a, top_b = st.columns([2, 1])

with top_a:
    st.subheader("Market Scanner")

    st.write(
        "Daily technical ranking with transparent rules, "
        "entry zone, stop and targets."
    )

with top_b:
    if st.button(
        "🔄 Run scan now",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("Scanning the Saudi watchlist..."):
            result = run_daily_scan(auto_open=True)

        st.success(
            f"Scan completed: "
            f"{result['scanned']} symbols, "
            f"{result['buy_count']} BUY signals."
        )

        st.rerun()


signals = get_signals(latest_only=True)

perf_all = get_performance()

trades = get_trades()


if (
    not trades.empty
    and "strategy_version" in trades.columns
):
    current_strategy_trades = trades[
        trades["strategy_version"] == STRATEGY_VERSION
    ].copy()
else:
    current_strategy_trades = pd.DataFrame()


perf_v2 = calculate_performance_from_trades(
    current_strategy_trades
)


c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "BUY today",
    int((signals.signal == "BUY").sum())
    if not signals.empty
    else 0,
)

c2.metric(
    "Open paper trades",
    int((trades.status == "OPEN").sum())
    if not trades.empty
    else 0,
)

c3.metric(
    "V2 Win rate",
    f"{perf_v2['win_rate']:.1f}%"
    if perf_v2["closed_trades"]
    else "—",
)

c4.metric(
    "V2 Paper P/L",
    f"{perf_v2['total_return']:+.2f}%"
    if perf_v2["closed_trades"]
    else "—",
)


scanner_tab, detail_tab, portfolio_tab, report_tab = st.tabs(
    [
        "🔥 Opportunities",
        "📊 Stock",
        "🧪 Paper Trades",
        "📈 30-Day Report",
    ]
)


with scanner_tab:
    if signals.empty:
        st.info(
            "No scan stored yet. Tap “Run scan now”. "
            "In cloud deployment the scheduled job runs "
            "automatically after the market closes."
        )

    else:
        min_score = st.slider(
            "Minimum score",
            0,
            100,
            60,
            5,
        )

        view = signals[
            signals.score >= min_score
        ].sort_values(
            "score",
            ascending=False,
        )

        for _, r in view.iterrows():
            css = (
                "buy"
                if r.signal == "BUY"
                else "watch"
                if r.signal == "WATCH"
                else "avoid"
                if r.signal == "AVOID"
                else ""
            )

            emoji = (
                "🟢"
                if r.signal == "BUY"
                else "🟡"
                if r.signal == "WATCH"
                else "🔴"
                if r.signal == "AVOID"
                else "⚪"
            )

            st.markdown(
                f"""
                <div class="signal-card {css}">
                <b>
                    {emoji} {r.symbol} — {r.get('name', '')}
                </b>
                <br>

                <span style="font-size:1.35rem">
                    <b>{r.signal}</b>
                    &nbsp;
                    {r.score:.0f}/100
                </span>
                <br>

                Price:
                <b>SAR {r.price:.2f}</b>
                &nbsp; | &nbsp;
                Entry:
                {r.entry_low:.2f}–{r.entry_high:.2f}
                <br>

                Stop:
                {r.stop:.2f}
                &nbsp; | &nbsp;
                T1:
                {r.target1:.2f}
                &nbsp; | &nbsp;
                T2:
                {r.target2:.2f}
                <br>

                <span class="small">
                    {r.reasons or ''}
                </span>
                </div>
                """,
                unsafe_allow_html=True,
            )


with detail_tab:
    symbol = st.selectbox(
        "Choose stock",
        universe.symbol.tolist(),
    )

    try:
        d = add_indicators(
            fetch_history(symbol, "2y")
        ).tail(240)

        fig = go.Figure()

        fig.add_trace(
            go.Candlestick(
                x=d.index,
                open=d.Open,
                high=d.High,
                low=d.Low,
                close=d.Close,
                name="Price",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=d.index,
                y=d.SMA20,
                name="SMA20",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=d.index,
                y=d.SMA50,
                name="SMA50",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=d.index,
                y=d.SMA200,
                name="SMA200",
            )
        )

        fig.update_layout(
            height=520,
            margin=dict(
                l=5,
                r=5,
                t=15,
                b=5,
            ),
            xaxis_rangeslider_visible=False,
            legend_orientation="h",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        latest = score_latest(d)

        if latest:
            a, b, c = st.columns(3)

            a.metric(
                "Score",
                f"{latest['score']:.0f}/100",
            )

            b.metric(
                "RSI",
                latest["rsi"],
            )

            c.metric(
                "Relative volume",
                f"{latest['rvol']:.2f}x",
            )

            st.write(
                "**Why this score:**",
                latest["reasons"],
            )

    except Exception as e:
        st.error(
            f"Could not load {symbol}: {e}"
        )


with portfolio_tab:
    if trades.empty:
        st.info(
            "No paper trades yet. "
            "BUY signals are automatically "
            "added by the daily runner."
        )

    else:
        show_cols = [
            c
            for c in [
                "opened_at",
                "symbol",
                "entry",
                "stop",
                "target1",
                "target2",
                "status",
                "closed_at",
                "exit",
                "pnl_pct",
                "outcome",
                "signal_date",
                "strategy_version",
            ]
            if c in trades.columns
        ]

        st.dataframe(
            trades[show_cols],
            use_container_width=True,
            hide_index=True,
        )


with report_tab:
    st.subheader("30-Day Strategy Scorecard")

    st.caption(
        f"Current strategy version: {STRATEGY_VERSION}"
    )

    if current_strategy_trades.empty:
        st.info(
            "No V2 paper trades have been opened yet. "
            "Existing older trades are preserved but are "
            "excluded from the V2 performance test."
        )

    else:
        open_v2 = int(
            (
                current_strategy_trades.status
                == "OPEN"
            ).sum()
        )

        total_v2 = len(
            current_strategy_trades
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "V2 Trades",
            total_v2,
        )

        b.metric(
            "Open",
            open_v2,
        )

        c.metric(
            "Closed",
            perf_v2["closed_trades"],
        )

        d.metric(
            "Win rate",
            f"{perf_v2['win_rate']:.1f}%"
            if perf_v2["closed_trades"]
            else "—",
        )

        e, f, g = st.columns(3)

        e.metric(
            "Avg trade",
            f"{perf_v2['avg_pnl']:+.2f}%"
            if perf_v2["closed_trades"]
            else "—",
        )

        f.metric(
            "Compounded P/L",
            f"{perf_v2['total_return']:+.2f}%"
            if perf_v2["closed_trades"]
            else "—",
        )

        g.metric(
            "Profit factor",
            (
                f"{perf_v2['profit_factor']:.2f}"
                if perf_v2["profit_factor"]
                is not None
                else "—"
            ),
        )

        st.markdown("### V2 Trades")

        report_cols = [
            c
            for c in [
                "opened_at",
                "symbol",
                "entry",
                "stop",
                "target1",
                "target2",
                "status",
                "closed_at",
                "exit",
                "pnl_pct",
                "outcome",
                "signal_date",
                "strategy_version",
            ]
            if c in current_strategy_trades.columns
        ]

        st.dataframe(
            current_strategy_trades[
                report_cols
            ],
            use_container_width=True,
            hide_index=True,
        )

    old_trade_count = (
        len(trades) - len(current_strategy_trades)
        if not trades.empty
        else 0
    )

    if old_trade_count > 0:
        st.caption(
            f"{old_trade_count} older paper trade(s) "
            "are stored in the database but excluded "
            "from the V2 scorecard."
        )

    st.caption(
        "Strategy weights should remain unchanged during "
        "the 30-day live paper test except for technical "
        "bug fixes."
    )


st.divider()

st.caption(
    "Research and paper-trading prototype only. "
    "It does not execute brokerage orders or provide "
    "personalized financial advice."
)
