# Stock Scout AI — Dashboard English / Layout Update

This package updates the existing dashboard without touching the SQLite database.

Changes:
- Entire dashboard UI is English.
- The top-right status now shows `Online · Updated <date/time>`.
- Open-position columns:

  `# | Ticker | Shares | Invested Capital | Entry | Price | Stop | Target | P&L | P&L % | R | Days | Status | Chart`

- Closed-trade columns use the same order.
- Closed trades now expose Stop, Target, realized R, holding Days, and a normalized Status (`STOP`, `TARGET`, or `MANUAL`).
- Chart actions remain available for both open and closed rows and are icon-only.
- Currency / number formatting uses English / USD formatting.
- Position details and the chart modal are shown in English.

## Apply

From the repository root:

```powershell
python apply_dashboard_update.py
```

Then validate:

```powershell
python -m pytest -q
```

Then review:

```powershell
git status
```

Commit the dashboard changes only. Do not add `data/stock_scout.db` to this commit unless you intentionally want to publish a database change.

Suggested commit:

```powershell
git add dashboard scripts/build_dashboard.py apply_dashboard_update.py README_APPLICA_DASHBOARD.md
git commit -m "feat: update dashboard language and trade table layout"
git push origin main
```
