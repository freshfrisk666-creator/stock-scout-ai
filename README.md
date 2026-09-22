# Stock Scout AI

Stock Scout AI is a transparent, modular research pipeline for the S&P 500.

## V1 milestone

> Run one command → analyze the S&P 500 → return the top 10 opportunities with a traceable methodology, entry/stop/target, and paper-trading orders.

The first implementation deliberately starts with **M1 Data Engine + M2 Technical Engine**. AI intelligence, learning loops, challenger strategies, and richer data sources come later.

## Architecture

```text
S&P 500
   ↓
M1 Data Engine
   ↓
Scanner / Liquidity Filter
   ↓
M2 Technical Engine
   ↓
Technical Ranking
   ↓
Top 10
   ↓
Paper Portfolio
```

## Stack

- Python
- pandas / NumPy
- yfinance
- SQLite
- Jupyter / Google Colab

## Run locally

```bash
pip install -r requirements.txt
python main.py
```

## Colab

Open `notebooks/Stock_Scout_AI_V1.ipynb` in Google Colab after the repository is pushed to GitHub.

## Methodology

Each candidate exposes the raw inputs used by the technical engine: price, SMA20/50/200, RSI14, ATR14, momentum 21d/63d, volume ratio, breakout strength, component scores, total technical score, entry, stop, target, and risk/reward.

The paper portfolio currently uses equal-weight whole-share orders with residual cash left uninvested.

This is a research and paper-trading prototype, not investment advice.
