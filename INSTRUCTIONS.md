# Installazione Intraday Paper Trading V1

## Aggiungere al repository

- `runner/intraday_monitor.py`
- `tests/test_intraday_monitor.py`
- `.github/workflows/intraday_monitor.yml`

## Sostituire

- `.github/workflows/paper_trading.yml`
- `config/config.yaml`

Il file `config/config.yaml` del pacchetto è già completo e può sostituire quello esistente.

## Non modificare

- `main.py`
- `database/db.py`
- `portfolio/paper_trading.py`
- `notebooks/Stock_Scout_AI_V1.ipynb`
- `data/stock_scout.db`

## Dopo il caricamento

1. Commit/push su `main`.
2. Aprire **Actions** e verificare entrambi i workflow.
3. Avviare manualmente `intraday-paper-monitor` con **Run workflow** per il primo test.
4. Controllare il log: deve indicare lo stato della sessione, le barre scaricate e le eventuali chiusure.
5. Lasciare poi attivo lo scheduler.

## Comportamento

- Il workflow `paper-trading` continua a fare la selezione giornaliera del Top 10.
- `intraday-paper-monitor` non riscansiona lo S&P 500: controlla solo i ticker già OPEN.
- Le barre utilizzate per il controllo sono a 5 minuti, mentre il workflow parte ogni 15 minuti.
- Se una barra tocca contemporaneamente stop e target, viene scelto lo stop per evitare un'ipotesi ottimistica sull'ordine intrabar.
- Il `signal_snapshot` del BUY resta quello della posizione e viene copiato nel SELL.
- Gli ordini sono esclusivamente virtuali/paper.
