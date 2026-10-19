from __future__ import annotations

from pathlib import Path

ROOT = Path('.')
APP = ROOT / 'dashboard' / 'app.js'
INDEX = ROOT / 'dashboard' / 'index.html'
STYLE = ROOT / 'dashboard' / 'style.css'
CHART = ROOT / 'dashboard' / 'trade_chart.js'
BUILD = ROOT / 'scripts' / 'build_dashboard.py'


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f'Missing start marker for {label}: {start!r}')
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f'Missing end marker for {label}: {end!r}')
    return text[:a] + replacement + text[b:]


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8', newline='\n')
    print(f'UPDATED {path}')


def update_index() -> None:
    content = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stock Scout AI — Paper Portfolio</title>
  <link rel="stylesheet" href="style.css">
</head>

<body>
  <header class="topbar">
    <div>
      <h1>Stock Scout AI</h1>
      <p>Paper Portfolio Dashboard</p>
    </div>

    <div class="status">
      <span id="statusDot" class="status-dot"></span>
      <span id="statusText">Loading...</span>
      <span class="status-separator">·</span>
      <span id="updatedAt" class="status-updated">Updated —</span>
    </div>
  </header>

  <main class="container">
    <section class="summary-grid">
      <div class="card"><div class="card-label">Equity</div><div id="equity" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Cash</div><div id="cash" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Open P&amp;L</div><div id="unrealizedPnl" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Realized P&amp;L</div><div id="realizedPnl" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Total P&amp;L</div><div id="totalPnl" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Open Positions</div><div id="openPositions" class="card-value">—</div></div>
      <div class="card"><div class="card-label">Closed Trades</div><div id="closedPositions" class="card-value">—</div></div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>Open Positions</h2>
          <p>Current paper portfolio</p>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Ticker</th><th>Shares</th><th>Invested Capital</th>
              <th>Entry</th><th>Price</th><th>Stop</th><th>Target</th>
              <th>P&amp;L</th><th>P&amp;L %</th><th>R</th><th>Days</th>
              <th>Status</th><th>Chart</th>
            </tr>
          </thead>
          <tbody id="openTableBody"><tr><td colspan="14" class="empty">Loading...</td></tr></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>Closed Trades</h2>
          <p>Realized paper trades</p>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Ticker</th><th>Shares</th><th>Invested Capital</th>
              <th>Entry</th><th>Price</th><th>Stop</th><th>Target</th>
              <th>P&amp;L</th><th>P&amp;L %</th><th>R</th><th>Days</th>
              <th>Status</th><th>Chart</th>
            </tr>
          </thead>
          <tbody id="closedTableBody"><tr><td colspan="14" class="empty">Loading...</td></tr></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>Position Details</h2>
          <p>Select a position to view its details</p>
        </div>
      </div>
      <div id="detailContent" class="detail-empty">No position selected.</div>
    </section>
  </main>

  <div id="tradeChartModal" class="chart-modal" hidden>
    <div class="chart-modal-backdrop" onclick="closeTradeChart()"></div>
    <div class="chart-dialog" role="dialog" aria-modal="true" aria-labelledby="tradeChartTitle">
      <div class="chart-dialog-header">
        <div><h2 id="tradeChartTitle">Trade Chart</h2><p id="tradeChartSubtitle">Loading...</p></div>
        <div class="chart-dialog-actions">
          <button type="button" class="chart-action secondary" onclick="refreshTradeChart()">↻ Refresh</button>
          <button type="button" class="chart-action" onclick="downloadTradeChartPng()">↓ PNG</button>
          <button type="button" class="chart-action" onclick="downloadTradeChartCsv()">↓ CSV</button>
          <button type="button" class="chart-action close" onclick="closeTradeChart()">×</button>
        </div>
      </div>
      <div id="tradeChartStatus" class="trade-chart-status">Loading...</div>
      <div id="tradeChartCanvas" class="trade-chart-canvas"></div>
      <div id="tradeChartContext" class="trade-chart-context"></div>
      <div class="trade-chart-attribution">Charts powered by <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView Lightweight Charts</a>.</div>
    </div>
  </div>

  <footer><span>Stock Scout AI</span><span>Paper Trading · S&amp;P 500</span></footer>

  <script src="https://unpkg.com/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.min.js"></script>
  <script src="trade_chart.js"></script>
  <script src="app.js"></script>
</body>
</html>
'''
    write(INDEX, content)


def update_app() -> None:
    text = APP.read_text(encoding='utf-8')

    formatting = '''function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function num(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }) + "%";
}

'''
    text = replace_between(text, 'function money(value) {', 'function cls(value) {', formatting, 'formatting helpers')

    date_helpers = '''function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short"
  });
}

// ------------------------------------------------------------
// Status
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'function formatDate(value) {',
        '// ------------------------------------------------------------\n// Status\n// ------------------------------------------------------------\n',
        date_helpers,
        'date helpers',
    )

    open_renderer = '''function renderOpenPositions(positions) {
  const tbody = document.getElementById("openTableBody");

  if (!positions || positions.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="14" class="empty">No open positions.</td></tr>
    `;
    return;
  }

  tbody.innerHTML = positions.map((position, index) => {
    const pnl = Number(position.unrealized_pnl || 0);
    const pnlPct = Number(position.unrealized_return || 0);
    const currentR = Number(position.current_r || 0);
    const watch = currentR < 0;

    return `
      <tr class="position-row" data-id="${position.id}">
        <td>${position.rank ?? index + 1}</td>
        <td><strong>${position.ticker || "—"}</strong></td>
        <td>${num(position.shares, 0)}</td>
        <td>${money(position.notional)}</td>
        <td>${money(position.entry_price)}</td>
        <td>${money(position.mark_price)}</td>
        <td>${money(position.stop)}</td>
        <td>${money(position.target)}</td>
        <td class="${cls(pnl)}">${money(pnl)}</td>
        <td class="${cls(pnlPct)}">${pct(pnlPct)}</td>
        <td class="${cls(currentR)}">${num(currentR)}</td>
        <td>${num(position.holding_days, 0)}</td>
        <td><span class="badge ${watch ? "watch" : "open"}">${watch ? "WATCH" : "OPEN"}</span></td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".position-row").forEach(row => {
    row.addEventListener("click", () => {
      const id = Number(row.dataset.id);
      const position = positions.find(item => Number(item.id) === id);
      if (position) {
        selectedPosition = position;
        renderOpenDetail(position);
      }
    });
  });
}

// ------------------------------------------------------------
// Closed positions
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'function renderOpenPositions(positions) {',
        '// ------------------------------------------------------------\n// Closed positions\n// ------------------------------------------------------------\n',
        open_renderer,
        'open positions renderer',
    )

    closed_renderer = '''function renderClosedPositions(positions) {
  const tbody = document.getElementById("closedTableBody");

  if (!positions || positions.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="14" class="empty">No closed trades.</td></tr>
    `;
    return;
  }

  tbody.innerHTML = positions.map((position, index) => {
    const pnl = Number(position.realized_pnl || 0);
    const pnlPct = Number(position.realized_return || 0);
    const realizedR = Number(position.realized_r || 0);
    const status = position.status_label || "CLOSED";
    const statusClass = status === "TARGET" ? "target" : status === "STOP" ? "stop" : "closed";

    return `
      <tr class="position-row" data-id="${position.id}">
        <td>${position.rank ?? index + 1}</td>
        <td><strong>${position.ticker || "—"}</strong></td>
        <td>${num(position.shares, 0)}</td>
        <td>${money(position.notional)}</td>
        <td>${money(position.entry_price)}</td>
        <td>${money(position.exit_price)}</td>
        <td>${money(position.stop)}</td>
        <td>${money(position.target)}</td>
        <td class="${cls(pnl)}">${money(pnl)}</td>
        <td class="${cls(pnlPct)}">${pct(pnlPct)}</td>
        <td class="${cls(realizedR)}">${num(realizedR)}</td>
        <td>${num(position.holding_days, 0)}</td>
        <td><span class="badge ${statusClass}">${status}</span></td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".position-row").forEach(row => {
    row.addEventListener("click", () => {
      const id = Number(row.dataset.id);
      const position = positions.find(item => Number(item.id) === id);
      if (position) {
        selectedPosition = position;
        renderClosedDetail(position);
      }
    });
  });
}

// ------------------------------------------------------------
// Open detail
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'function renderClosedPositions(positions) {',
        '// ------------------------------------------------------------\n// Open detail\n// ------------------------------------------------------------\n',
        closed_renderer,
        'closed positions renderer',
    )

    open_detail = '''function renderOpenDetail(position) {
  const container = document.getElementById("detailContent");
  const pnl = Number(position.unrealized_pnl || 0);
  const pnlPct = Number(position.unrealized_return || 0);
  const currentR = Number(position.current_r || 0);
  const watch = currentR < 0;

  container.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item"><span>Ticker</span><strong>${position.ticker || "—"}</strong></div>
      <div class="detail-item"><span>Shares</span><strong>${num(position.shares, 0)}</strong></div>
      <div class="detail-item"><span>Invested Capital</span><strong>${money(position.notional)}</strong></div>
      <div class="detail-item"><span>Status</span><strong class="${watch ? "negative" : "positive"}">${watch ? "WATCH" : "OPEN"}</strong></div>
      <div class="detail-item"><span>Strategy</span><strong>${position.strategy_type || "—"}</strong></div>
      <div class="detail-item"><span>Horizon</span><strong>${position.planned_horizon_sessions ?? "—"} sessions</strong></div>
      <div class="detail-item"><span>Entry Date</span><strong>${formatDate(position.entry_date)}</strong></div>
      <div class="detail-item"><span>Entry</span><strong>${money(position.entry_price)}</strong></div>
      <div class="detail-item"><span>Current Price</span><strong>${money(position.mark_price)}</strong></div>
      <div class="detail-item"><span>Price Updated</span><strong>${formatDateTime(position.price_updated_at)}</strong></div>
      <div class="detail-item"><span>P&amp;L</span><strong class="${cls(pnl)}">${money(pnl)}</strong></div>
      <div class="detail-item"><span>P&amp;L %</span><strong class="${cls(pnlPct)}">${pct(pnlPct)}</strong></div>
      <div class="detail-item"><span>Current R</span><strong class="${cls(currentR)}">${num(currentR)}</strong></div>
      <div class="detail-item"><span>Stop</span><strong>${money(position.stop)}</strong></div>
      <div class="detail-item"><span>Target</span><strong>${money(position.target)}</strong></div>
      <div class="detail-item"><span>Days</span><strong>${num(position.holding_days, 0)}</strong></div>
    </div>
    <div class="detail-section">
      <h3>Signal Metrics</h3>
      ${buildSignalMetrics(position)}
    </div>
  `;
}

// ------------------------------------------------------------
// Closed detail
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'function renderOpenDetail(position) {',
        '// ------------------------------------------------------------\n// Closed detail\n// ------------------------------------------------------------\n',
        open_detail,
        'open detail',
    )

    closed_detail = '''function renderClosedDetail(position) {
  const container = document.getElementById("detailContent");
  const pnl = Number(position.realized_pnl || 0);
  const pnlPct = Number(position.realized_return || 0);
  const realizedR = Number(position.realized_r || 0);

  container.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item"><span>Ticker</span><strong>${position.ticker || "—"}</strong></div>
      <div class="detail-item"><span>Shares</span><strong>${num(position.shares, 0)}</strong></div>
      <div class="detail-item"><span>Invested Capital</span><strong>${money(position.notional)}</strong></div>
      <div class="detail-item"><span>Strategy</span><strong>${position.strategy_type || "—"}</strong></div>
      <div class="detail-item"><span>Horizon</span><strong>${position.planned_horizon_sessions ?? "—"} sessions</strong></div>
      <div class="detail-item"><span>Rank</span><strong>${position.rank ?? "—"}</strong></div>
      <div class="detail-item"><span>Entry Date</span><strong>${formatDate(position.entry_date)}</strong></div>
      <div class="detail-item"><span>Entry</span><strong>${money(position.entry_price)}</strong></div>
      <div class="detail-item"><span>Exit Price</span><strong>${money(position.exit_price)}</strong></div>
      <div class="detail-item"><span>Stop</span><strong>${money(position.stop)}</strong></div>
      <div class="detail-item"><span>Target</span><strong>${money(position.target)}</strong></div>
      <div class="detail-item"><span>Realized P&amp;L</span><strong class="${cls(pnl)}">${money(pnl)}</strong></div>
      <div class="detail-item"><span>P&amp;L %</span><strong class="${cls(pnlPct)}">${pct(pnlPct)}</strong></div>
      <div class="detail-item"><span>Realized R</span><strong class="${cls(realizedR)}">${num(realizedR)}</strong></div>
      <div class="detail-item"><span>Days</span><strong>${num(position.holding_days, 0)}</strong></div>
      <div class="detail-item"><span>Status</span><strong>${position.status_label || "CLOSED"}</strong></div>
      <div class="detail-item"><span>Exit Date</span><strong>${formatDate(position.exit_date)}</strong></div>
    </div>
    <div class="detail-section">
      <h3>Signal Metrics</h3>
      ${buildSignalMetrics(position)}
    </div>
  `;
}

// ------------------------------------------------------------
// Load dashboard data
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'function renderClosedDetail(position) {',
        '// ------------------------------------------------------------\n// Load dashboard data\n// ------------------------------------------------------------\n',
        closed_detail,
        'closed detail',
    )

    loader = '''async function loadDashboard() {
  try {
    setStatus("Loading...", true);

    const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    dashboardData = data;

    renderSummary(data);
    renderOpenPositions(data.open || []);
    renderClosedPositions(data.closed || []);

    const updatedAt = document.getElementById("updatedAt");
    if (updatedAt) {
      updatedAt.textContent = data.generated_at
        ? `Updated ${formatDateTime(data.generated_at)}`
        : "Updated —";
    }

    setStatus("Online", true);
  } catch (error) {
    console.error("Dashboard data load error:", error);

    const updatedAt = document.getElementById("updatedAt");
    if (updatedAt) updatedAt.textContent = "Updated —";

    setStatus("Data Error", false);

    document.getElementById("openTableBody").innerHTML = `
      <tr><td colspan="14" class="empty">Unable to load dashboard data.</td></tr>
    `;

    document.getElementById("closedTableBody").innerHTML = `
      <tr><td colspan="14" class="empty">Unable to load dashboard data.</td></tr>
    `;
  }
}

// ------------------------------------------------------------
// Auto refresh
// ------------------------------------------------------------

'''
    text = replace_between(
        text,
        'async function loadDashboard() {',
        '// ------------------------------------------------------------\n// Auto refresh\n// ------------------------------------------------------------\n',
        loader,
        'dashboard loader',
    )

    write(APP, text)


def update_style() -> None:
    text = STYLE.read_text(encoding='utf-8')
    additions = '''\n\n/* Dashboard English / status timestamp */\n.status-separator {\n  color: var(--muted);\n  opacity: 0.6;\n}\n\n.status-updated {\n  color: var(--muted);\n}\n\n.badge.target {\n  color: var(--positive);\n  background: rgba(53, 201, 139, 0.10);\n  border: 1px solid rgba(53, 201, 139, 0.25);\n}\n\n.badge.stop {\n  color: var(--negative);\n  background: rgba(255, 79, 109, 0.10);\n  border: 1px solid rgba(255, 79, 109, 0.25);\n}\n\n.badge.closed {\n  color: var(--muted);\n  background: rgba(141, 153, 168, 0.08);\n  border: 1px solid rgba(141, 153, 168, 0.20);\n}\n\n.chart-btn {\n  width: 32px;\n  height: 30px;\n  padding: 0;\n  gap: 0;\n  font-size: 14px;\n  line-height: 1;\n}\n'''
    if '/* Dashboard English / status timestamp */' not in text:
        text += additions
    write(STYLE, text)


def update_chart() -> None:
    text = CHART.read_text(encoding='utf-8')
    replacements = {
        'toLocaleString("it-IT"': 'toLocaleString("en-US"',
        '<button type="button" class="chart-btn">📊 Chart</button>': '<button type="button" class="chart-btn" title="Open chart" aria-label="Open chart">📊</button>',
        'chartStatus("Caricamento del tracciato...");': 'chartStatus("Loading chart...");',
        '"Tracciato aggiornato: "': '"Chart updated: "',
        'chartStatus("Errore caricamento chart: " + error.message, true);': 'chartStatus("Chart loading error: " + error.message, true);',
        '"Trade chiuso"': '"Closed Trade"',
        '"Posizione aperta"': '"Open Position"',
        '"Nessuna divergenza RSI significativa"': '"No significant RSI divergence"',
        '"Bullish divergence presente"': '"Bullish divergence present"',
        '"Bearish divergence presente"': '"Bearish divergence present"',
        '"Bottom analysis"': '"Divergence Analysis"',
        '"VIX media trade"': '"Average VIX during trade"',
        '"VIX uscita"': '"VIX at exit"',
        '"Risultato"': '"Result"',
        'chartStatus("Libreria grafica non disponibile.", true);': 'chartStatus("Chart library unavailable.", true);',
        'chartStatus("Dati storici non disponibili.", true);': 'chartStatus("Historical data unavailable.", true);',
        'chartStatus("Aggiornamento del tracciato...");': 'chartStatus("Updating chart...");',
        '"Mostra / nascondi "': '"Show / hide "',
        'Il VIX è usato solo come contesto del mercato. Non viene disegnato nel chart e non modifica lo scoring. Le divergenze sono rilevate su prezzo + RSI14 e sono un\'analisi diagnostica, non un segnale automatico. La linea tratteggiata è una possibile traiettoria verso il target, non una previsione certa.': 'VIX is shown as market context only. It is not plotted and does not affect scoring. Divergences are diagnostic analysis based on price + RSI14, not automatic signals. The dashed line is a possible path toward the target, not a forecast.',
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
    write(CHART, text)


def update_build() -> None:
    text = BUILD.read_text(encoding='utf-8')
    needle = '''        closed.append(\n            {\n                "id": int(row.id),\n'''
    insert = '''        stop = clean(row.stop)\n        target = clean(row.target)\n\n        realized_r = None\n        if exit_price is not None and stop is not None and float(entry) > float(stop):\n            realized_r = (float(exit_price) - float(entry)) / (float(entry) - float(stop))\n\n        entry_dt = pd.to_datetime(row.entry_date, utc=True, errors="coerce")\n        exit_dt = pd.to_datetime(row.exit_date, utc=True, errors="coerce")\n        holding_days = None\n        if pd.notna(entry_dt) and pd.notna(exit_dt):\n            holding_days = max(0, (exit_dt - entry_dt).total_seconds() / 86400)\n\n        reason = str(row.close_reason or "")\n        status_label = {\n            "TARGET_CLOSE": "TARGET",\n            "STOP_CLOSE": "STOP",\n            "MANUAL_CLOSE": "MANUAL",\n        }.get(\n            reason,\n            reason.replace("_", " ").strip().title() if reason else "CLOSED",\n        )\n\n        closed.append(\n            {\n                "id": int(row.id),\n'''
    if needle not in text:
        raise RuntimeError('Could not find closed-trade JSON block in scripts/build_dashboard.py')
    text = text.replace(needle, insert, 1)

    old = '''                "realized_return": realized_return,\n                "close_reason": clean(row.close_reason),\n'''
    new = '''                "realized_return": realized_return,\n                "stop": stop,\n                "target": target,\n                "realized_r": realized_r,\n                "holding_days": holding_days,\n                "status_label": status_label,\n                "close_reason": clean(row.close_reason),\n'''
    if old not in text:
        raise RuntimeError('Could not find closed-trade fields in scripts/build_dashboard.py')
    text = text.replace(old, new, 1)
    write(BUILD, text)


def main() -> None:
    required = [APP, INDEX, STYLE, CHART, BUILD]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit('Missing expected files:\n' + '\n'.join(missing))

    update_index()
    update_app()
    update_style()
    update_chart()
    update_build()

    print('\nDashboard update applied.')
    print('Database was NOT modified.')
    print('Run the dashboard workflow after committing the changed files.')


if __name__ == '__main__':
    main()
