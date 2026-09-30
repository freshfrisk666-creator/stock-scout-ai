# Stock Scout AI — Intraday Paper Trading V1

Questo pacchetto aggiunge il monitoraggio intraday senza rifare lo scanner S&P 500 a ogni ciclo.

## Architettura

- **Daily runner**: seleziona il Top 10 e gestisce gli ingressi una volta al giorno dopo la chiusura USA.
- **Intraday monitor**: ogni 15 minuti controlla soltanto le posizioni OPEN, usando barre Yahoo Finance da 5 minuti.
- **Exit logic**: se una barra tocca lo stop o il target, viene registrata una SELL virtuale al livello di stop/target.
- Se la stessa barra tocca sia stop sia target, viene usato lo **STOP** perché l'ordine intrabar non è osservabile dalla barra OHLC.
- Lo `signal_snapshot` del BUY viene copiato nel SELL.

## File da aggiungere/sostituire

Aggiungere:

- `runner/intraday_monitor.py`
- `tests/test_intraday_monitor.py`
- `.github/workflows/intraday_monitor.yml`

Aggiornare:

- `.github/workflows/paper_trading.yml`
- `config/config.yaml` aggiungendo il blocco `intraday` contenuto in `config.yaml` di questo pacchetto.

Non serve modificare il notebook in questa fase.

## Dati

yfinance supporta intervalli intraday come `5m` e `15m`; i dati intraday hanno una finestra storica limitata, mentre qui usiamo solo `period="1d"` per il monitor corrente. La fetch riguarda solo i ticker OPEN. 

## Esecuzione

Il workflow `intraday-paper-monitor` può essere avviato anche manualmente da GitHub Actions con `workflow_dispatch`. Lo scheduler è configurato ogni 15 minuti tra le 09:00 e le 16:00 America/New_York; il codice verifica comunque che la sessione cash sia attiva prima di fare il monitoraggio.

GitHub Actions supporta schedule timezone-aware e un intervallo minimo di 5 minuti; i job schedulati possono comunque partire in ritardo sotto carico.

## Nota di simulazione

Questo è **paper trading**: non invia ordini a un broker e non rappresenta un sistema di esecuzione live. GitHub Actions non va considerato un motore di esecuzione con latenza garantita.
