# Signal Attribution notebook update

The supplied `notebooks/Stock_Scout_AI_V1.ipynb` is already updated for Signal Attribution.

It keeps the existing Colab setup and adds:

- `signal_snapshot` visibility on closed trades.
- A database query showing BUY/SELL attribution records.
- An explanation that the complete Top10 row is persisted at entry and copied unchanged to SELL.

In Colab, refresh the repository checkout, then run the notebook from the top. Do not delete `data/stock_scout.db`; the new schema migrates it in place.
