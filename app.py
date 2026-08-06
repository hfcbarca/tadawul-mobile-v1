
from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from engine import add_indicators, score_latest
from data_source import fetch_history
from db import init_db, save_signals, get_signals, get_trades, get_performance
from daily_runner import run_daily_scan

st.set_page_config(page_title="Tadawul V1", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
init_db()
BASE = Path(__file__).parent

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1250px;}
[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.22); padding:12px; border-radius:14px;}
.signal-card {border:1px solid rgba(128,128,128,.25); border-radius:16px; padding:15px; margin-bottom:12px;}
.buy {border-left:6px solid #19a15f}.watch {border-left:6px solid #e0a100}.avoid {border-left:6px solid #d64545}
.small {opacity:.75;font-size:.88rem}
@media (max-width: 700px) {
  .block-container {padding-left:.8rem; padding-right:.8rem;}
  h1 {font-size:1.7rem !important;}
  [data-testid="stMetricValue"] {font-size:1.35rem;}
}
</style>
""", unsafe_allow_html=True)

st.title("📈 Tadawul V1")
st.caption("30-Day Paper Test • Saudi market decision-support tool • No real-money execution")

universe = pd.read_csv(BASE / "tickers.csv")

top_a, top_b = st.columns([2,1])
with top_a:
    st.subheader("Market Scanner")
    st.write("Daily technical ranking with transparent rules, entry zone, stop and targets.")
with top_b:
    if st.button("🔄 Run scan now", type="primary", use_container_width=True):
        with st.spinner("Scanning the Saudi watchlist..."):
            result = run_daily_scan(auto_open=True)
        st.success(f"Scan completed: {result['scanned']} symbols, {result['buy_count']} BUY signals.")
        st.rerun()

signals = get_signals(latest_only=True)
perf = get_performance()
trades = get_trades()

c1,c2,c3,c4 = st.columns(4)
c1.metric("BUY today", int((signals.signal=="BUY").sum()) if not signals.empty else 0)
c2.metric("Open paper trades", int((trades.status=="OPEN").sum()) if not trades.empty else 0)
c3.metric("Win rate", f"{perf['win_rate']:.1f}%" if perf["closed_trades"] else "—")
c4.metric("Paper P/L", f"{perf['total_return']:+.2f}%" if perf["closed_trades"] else "—")

scanner_tab, detail_tab, portfolio_tab, report_tab = st.tabs(["🔥 Opportunities","📊 Stock","🧪 Paper Trades","📈 30-Day Report"])

with scanner_tab:
    if signals.empty:
        st.info("No scan stored yet. Tap “Run scan now”. In cloud deployment the scheduled job runs automatically after the market closes.")
    else:
        min_score = st.slider("Minimum score", 0, 100, 60, 5)
        view = signals[signals.score >= min_score].sort_values("score", ascending=False)
        for _, r in view.iterrows():
            css = "buy" if r.signal=="BUY" else "watch" if r.signal=="WATCH" else "avoid" if r.signal=="AVOID" else ""
            emoji = "🟢" if r.signal=="BUY" else "🟡" if r.signal=="WATCH" else "🔴" if r.signal=="AVOID" else "⚪"
            st.markdown(
                f"""<div class="signal-card {css}">
                <b>{emoji} {r.symbol} — {r.get('name','')}</b><br>
                <span style="font-size:1.35rem"><b>{r.signal}</b> &nbsp; {r.score:.0f}/100</span><br>
                Price: <b>SAR {r.price:.2f}</b> &nbsp; | &nbsp; Entry: {r.entry_low:.2f}–{r.entry_high:.2f}<br>
                Stop: {r.stop:.2f} &nbsp; | &nbsp; T1: {r.target1:.2f} &nbsp; | &nbsp; T2: {r.target2:.2f}<br>
                <span class="small">{r.reasons or ''}</span>
                </div>""", unsafe_allow_html=True
            )

with detail_tab:
    symbol = st.selectbox("Choose stock", universe.symbol.tolist())
    try:
        d = add_indicators(fetch_history(symbol, "2y")).tail(240)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"))
        fig.add_trace(go.Scatter(x=d.index, y=d.SMA20, name="SMA20"))
        fig.add_trace(go.Scatter(x=d.index, y=d.SMA50, name="SMA50"))
        fig.add_trace(go.Scatter(x=d.index, y=d.SMA200, name="SMA200"))
        fig.update_layout(height=520, margin=dict(l=5,r=5,t=15,b=5), xaxis_rangeslider_visible=False, legend_orientation="h")
        st.plotly_chart(fig, use_container_width=True)
        latest = score_latest(d)
        if latest:
            a,b,c = st.columns(3)
            a.metric("Score", f"{latest['score']:.0f}/100")
            b.metric("RSI", latest["rsi"])
            c.metric("Relative volume", f"{latest['rvol']:.2f}x")
            st.write("**Why this score:**", latest["reasons"])
    except Exception as e:
        st.error(f"Could not load {symbol}: {e}")

with portfolio_tab:
    if trades.empty:
        st.info("No paper trades yet. BUY signals are automatically added by the daily runner.")
    else:
        show_cols = [c for c in ["opened_at","symbol","entry","stop","target1","target2","status","closed_at","exit","pnl_pct","outcome"] if c in trades.columns]
        st.dataframe(trades[show_cols], use_container_width=True, hide_index=True)

with report_tab:
    st.subheader("Paper-test scorecard")
    a,b,c,d = st.columns(4)
    a.metric("Closed", perf["closed_trades"])
    b.metric("Wins", perf["wins"])
    c.metric("Losses", perf["losses"])
    d.metric("Win rate", f"{perf['win_rate']:.1f}%")
    e,f,g = st.columns(3)
    e.metric("Avg trade", f"{perf['avg_pnl']:+.2f}%")
    f.metric("Compounded P/L", f"{perf['total_return']:+.2f}%")
    g.metric("Profit factor", f"{perf['profit_factor']:.2f}" if perf["profit_factor"] is not None else "—")
    st.caption("V1 uses fixed, auditable rules. Strategy weights should remain unchanged during the 30-day live paper test except for technical bug fixes.")

st.divider()
st.caption("Research and paper-trading prototype only. It does not execute brokerage orders or provide personalized financial advice.")
