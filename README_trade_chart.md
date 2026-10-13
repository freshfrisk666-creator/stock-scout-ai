# Stock Scout AI — Trade Chart V1.5

Pacchetto completo per la dashboard Trade Chart.

## Modifiche incluse

- Entry, Stop Loss, Target ed Exit con linee più sottili (2px).
- Fascia verde Entry → Target e fascia rossa Entry → Stop Loss.
- Zone SUPPORT e RESISTANCE trasparenti, con fallback sul recent structural low/high quando il clustering non produce una zona visibile.
- SMA20/SMA50/SMA200 attivabili/disattivabili tramite pulsanti.
- RSI14 in pannello inferiore.
- Bullish/Bearish RSI divergence con trendline graficamente allineate ai due pivot RSI.
- VIX usato solo come contesto, non tracciato nel grafico e non usato per cambiare lo scoring.
- Proiezione tratteggiata possibile verso il target, solo per trade aperti: parte dall'ultima chiusura disponibile e arriva al target come scenario visivo, non come previsione certa.
- Aggiorna preserva zoom e posizione orizzontale del chart.
- Il fit completo viene eseguito quando il chart viene aperto; chiusura + riapertura ripristina la vista completa.
- Pulsante Chart per trade aperti e chiusi.
- Pulsanti PNG e CSV.
- Stato dashboard ripristinato: OPEN oppure WATCH. WATCH = Current R < 0; non modifica lo stato reale del database e non chiude il trade.

## File da copiare nel repository

- `dashboard/index.html`
- `dashboard/app.js`
- `dashboard/style.css`
- `dashboard/trade_chart.js`
- `scripts/build_trade_charts.py`
- `.github/workflows/dashboard.yml`

`build_dashboard.py` non viene sostituito da questo pacchetto.

## Git

Prima di fare push, se il repository remoto può avere commit automatici:

```powershell
git fetch origin
git pull --rebase origin main
```

Poi:

```powershell
git add dashboard/index.html dashboard/app.js dashboard/style.css dashboard/trade_chart.js scripts/build_trade_charts.py .github/workflows/dashboard.yml README_trade_chart.md
git commit -m "Improve trade chart and restore open watch status"
git push origin main
```
