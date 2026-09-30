# Stock Scout AI — Trade Performance Report V1

Questa estensione aggiunge il report aggregato dei trade CLOSED sopra il modulo Trade Analysis V1.

## Nuovi file

- `analysis/trade_report.py`
- `tests/test_trade_report.py`
- `notebooks/Stock_Scout_AI_V1.ipynb` aggiornato con la sezione 10

## Metriche

Il report calcola:

- numero totale di trade
- WIN / LOSS / FLAT
- win rate
- P&L realizzato totale e medio
- media dei vincitori e dei perdenti
- rendimento medio
- R-multiple medio
- durata media
- migliore / peggiore trade
- profit factor
- maximum drawdown sul P&L cumulato

Inoltre confronta i punteggi `technical_score`, `trend_score`, `momentum_score`, `rsi_score`, `volume_score` e `breakout_score` per outcome.

Le differenze sono descrittive e non implicano causalità.
