# Stock Scout AI — Trade Analysis V1

Aggiunge la prima fase di analisi post-trade senza modificare il ranking M1/M2.

## File da aggiungere/sostituire

- `analysis/__init__.py` — nuovo package
- `analysis/trade_analysis.py` — analisi deterministica delle posizioni CLOSED
- `tests/test_trade_analysis.py` — test della nuova analisi
- `notebooks/Stock_Scout_AI_V1.ipynb` — aggiunta della sezione `9. Trade Analysis — WHY DID IT WIN / LOSE?`

## Cosa produce

Per ogni posizione `CLOSED` legge il `signal_snapshot` salvato all'ingresso e calcola:

- WIN / LOSS / FLAT
- entry / exit / stop / target
- P&L e rendimento percentuale
- R-multiple realizzato
- durata del trade
- rank e punteggi del segnale
- componenti forti/deboli del segnale
- una spiegazione testuale osservazionale

Non viene modificata la strategia di ranking e non viene assunto che un singolo fattore abbia causato il risultato.

## Colab

Il notebook aggiornato importa:

```python
from analysis.trade_analysis import load_closed_trade_analysis
```

Se non esistono ancora trade `CLOSED`, la cella mostra semplicemente:

`No CLOSED trades available yet.`

Questo è normale: l'analisi diventa popolata quando una posizione raggiunge stop o target.

## Test

Nel repository completo eseguire:

```bash
pytest -q
```

Test specifici della nuova funzione:

```bash
pytest -q tests/test_trade_analysis.py
```
