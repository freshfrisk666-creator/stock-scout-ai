# Stock Scout AI — Automated Paper Trading V1

Questa estensione trasforma il runner manuale in un ciclo di **paper trading giornaliero automatizzato** usando GitHub Actions.

## Cosa aggiunge

- `runner/daily_runner.py`: esegue un ciclo completo chiamando `main.run_pipeline()`.
- `.github/workflows/paper_trading.yml`: avvia il ciclo nei giorni feriali alle 22:30 UTC e permette anche un avvio manuale con **Run workflow**.
- `.gitignore`: mantiene `data/stock_scout.db` versionabile, così lo stato del portfolio può passare da una run alla successiva.
- `tests/test_daily_runner.py`: test del nuovo entrypoint.

## Flusso

```text
GitHub Actions
      ↓
runner.daily_runner
      ↓
main.run_pipeline()
      ↓
market data → scanner → technical → Top 10
      ↓
evaluate exits → sync new positions
      ↓
SQLite data/stock_scout.db
      ↓
Git commit del DB
```

## Importante

Questa è ancora **paper trading**: usa dati di mercato per simulare BUY/SELL e P&L, ma non invia ordini a un broker e non muove denaro reale.

Il cron è giornaliero, non intraday. GitHub Actions può avviare i job con ritardi; non è adatto a un motore tick-by-tick o a esecuzione con garanzie di latenza.

## Installazione nel repository

Aggiungere:

```text
runner/__init__.py
runner/daily_runner.py
.github/workflows/paper_trading.yml
 tests/test_daily_runner.py
 data/.gitkeep
```

e sostituire `.gitignore` con quello incluso in questo pacchetto.

## Primo test

Dopo il commit/push, aprire:

**GitHub → Actions → paper-trading → Run workflow**

Il workflow esegue un solo ciclo e poi prova a committare `data/stock_scout.db` su `main`.

Dopo la prima esecuzione, la pagina del repository dovrebbe mostrare il database persistente dentro `data/`.
