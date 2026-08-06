
# Tadawul Mobile V1 — 30 Day Paper Test

Mobile-first Streamlit web app for Saudi stock scanning and paper trading.

## What it does
- Scans the symbols in `tickers.csv`
- Calculates SMA20/50/200, RSI14, MACD, ATR, relative volume and breakout structure
- Scores each stock from 0–100
- Stores daily signals
- Automatically opens up to 5 highest-scoring BUY paper trades per scan
- Automatically checks open trades against Stop / Target 1 / Target 2
- Shows win rate, average trade, compounded paper P/L and profit factor
- Never connects to a broker or places real orders

## Paper-test convention
Signals are generated using daily bars. V1 records a paper entry at the signal close.
For a later daily bar, if both stop and target could have been touched on the same bar,
the simulator conservatively assumes the stop was hit first.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Render
1. Put this folder in a GitHub repository.
2. In Render choose **New > Blueprint** and connect the repository.
3. Render reads `render.yaml` and creates:
   - Web service
   - PostgreSQL database
   - Scheduled daily scanner
4. Open the web-service URL on your phone and add it to the home screen.

The included schedule is `13:30 UTC` Sunday–Thursday, equivalent to `16:30 Asia/Riyadh`.
Change it in `render.yaml` if desired.

## Important
Yahoo Finance is used only as the default prototype data adapter. Before relying on this
for live investment decisions, replace it with a licensed/reliable Saudi market data feed
and validate all signal and corporate-action handling.
