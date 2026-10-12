const DATA_URL = "data.json";

let dashboardData = null;
let selectedPosition = null;

// ------------------------------------------------------------
// Formatting helpers
// ------------------------------------------------------------

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }) + " $";
}

function num(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }) + "%";
}

function cls(value) {
  const n = Number(value);

  if (Number.isNaN(n)) {
    return "";
  }

  if (n > 0) {
    return "positive";
  }

  if (n < 0) {
    return "negative";
  }

  return "";
}

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("it-IT");
}

// ------------------------------------------------------------
// Status
// ------------------------------------------------------------

function setStatus(text, online = true) {
  const statusText = document.getElementById("statusText");
  const statusDot = document.getElementById("statusDot");

  if (statusText) {
    statusText.textContent = text;
  }

  if (statusDot) {
    statusDot.classList.toggle("offline", !online);
  }
}

// ------------------------------------------------------------
// Summary
// ------------------------------------------------------------

function renderSummary(data) {
  const summary = data.summary || {};

  const equity = Number(summary.equity || 0);
  const cash = Number(summary.cash || 0);
  const unrealizedPnl = Number(summary.unrealized_pnl || 0);
  const realizedPnl = Number(summary.realized_pnl || 0);

  const totalPnl = unrealizedPnl + realizedPnl;

  document.getElementById("equity").textContent = money(equity);
  document.getElementById("cash").textContent = money(cash);

  const unrealizedElement = document.getElementById("unrealizedPnl");
  const realizedElement = document.getElementById("realizedPnl");
  const totalElement = document.getElementById("totalPnl");

  unrealizedElement.textContent = money(unrealizedPnl);
  realizedElement.textContent = money(realizedPnl);
  totalElement.textContent = money(totalPnl);

  unrealizedElement.className = `card-value ${cls(unrealizedPnl)}`;
  realizedElement.className = `card-value ${cls(realizedPnl)}`;
  totalElement.className = `card-value ${cls(totalPnl)}`;

  document.getElementById("openPositions").textContent =
    num(summary.open_positions || 0, 0);

  document.getElementById("closedPositions").textContent =
    num(summary.closed_positions || 0, 0);
}

// ------------------------------------------------------------
// Signal metrics
// ------------------------------------------------------------

function buildSignalMetrics(position) {
  const signal = position.signal || {};

  return `
    <div class="signal-grid">

      <div>
        <span>Technical Score</span>
        <strong>${num(signal.technical_score)}</strong>
      </div>

      <div>
        <span>Trend</span>
        <strong>${num(signal.trend_score)}</strong>
      </div>

      <div>
        <span>Momentum</span>
        <strong>${num(signal.momentum_score)}</strong>
      </div>

      <div>
        <span>RSI</span>
        <strong>${num(signal.rsi_score)}</strong>
      </div>

      <div>
        <span>Volume</span>
        <strong>${num(signal.volume_score)}</strong>
      </div>

      <div>
        <span>Breakout</span>
        <strong>${num(signal.breakout_score)}</strong>
      </div>

      <div>
        <span>Risk / Reward</span>
        <strong>${num(signal.risk_reward)}</strong>
      </div>

    </div>
  `;
}

// ------------------------------------------------------------
// Open positions
// ------------------------------------------------------------

function renderOpenPositions(positions) {
  const tbody = document.getElementById("openTableBody");

  if (!positions || positions.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="13" class="empty">
          Nessuna posizione aperta.
        </td>
      </tr>
    `;

    return;
  }

  tbody.innerHTML = positions.map((position, index) => {

    const pnl = Number(position.unrealized_pnl || 0);
    const pnlPct = Number(position.unrealized_return || 0);
    const currentR = Number(position.current_r || 0);

    return `
      <tr
        class="position-row"
        data-id="${position.id}"
      >

        <td>${position.rank ?? index + 1}</td>

        <td>
          <strong>${position.ticker || "—"}</strong>
        </td>

        <td>
          ${num(position.shares, 0)}
        </td>

        <td>
          ${money(position.notional)}
        </td>

        <td>
          ${money(position.entry_price)}
        </td>

        <td>
          ${money(position.mark_price)}
        </td>

        <td class="${cls(pnl)}">
          ${money(pnl)}
        </td>

        <td class="${cls(pnlPct)}">
          ${pct(pnlPct)}
        </td>

        <td class="${cls(currentR)}">
          ${num(currentR)}
        </td>

        <td>
          ${money(position.stop)}
        </td>

        <td>
          ${money(position.target)}
        </td>

        <td>
          ${num(position.holding_days, 0)}
        </td>

        <td>
          <span class="badge open">OPEN</span>
        </td>

      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".position-row").forEach(row => {
    row.addEventListener("click", () => {
      const id = Number(row.dataset.id);

      const position = positions.find(
        item => Number(item.id) === id
      );

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

function renderClosedPositions(positions) {
  const tbody = document.getElementById("closedTableBody");

  if (!positions || positions.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="empty">
          Nessun trade chiuso.
        </td>
      </tr>
    `;

    return;
  }

  tbody.innerHTML = positions.map(position => {

    const pnl = Number(position.realized_pnl || 0);
    const pnlPct = Number(position.realized_return || 0);

    return `
      <tr
        class="position-row"
        data-id="${position.id}"
      >

        <td>
          <strong>${position.ticker || "—"}</strong>
        </td>

        <td>
          ${num(position.shares, 0)}
        </td>

        <td>
          ${money(position.notional)}
        </td>

        <td>
          ${money(position.entry_price)}
        </td>

        <td>
          ${money(position.exit_price)}
        </td>

        <td class="${cls(pnl)}">
          ${money(pnl)}
        </td>

        <td class="${cls(pnlPct)}">
          ${pct(pnlPct)}
        </td>

        <td>
          ${position.close_reason || "—"}
        </td>

        <td>
          ${formatDate(position.exit_date)}
        </td>

      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".position-row").forEach(row => {
    row.addEventListener("click", () => {
      const id = Number(row.dataset.id);

      const position = positions.find(
        item => Number(item.id) === id
      );

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

function renderOpenDetail(position) {
  const container = document.getElementById("detailContent");

  const pnl = Number(position.unrealized_pnl || 0);
  const pnlPct = Number(position.unrealized_return || 0);
  const currentR = Number(position.current_r || 0);

  container.innerHTML = `
    <div class="detail-grid">

      <div class="detail-item">
        <span>Ticker</span>
        <strong>${position.ticker || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Azioni</span>
        <strong>${num(position.shares, 0)}</strong>
      </div>

      <div class="detail-item">
        <span>Capitale investito</span>
        <strong>${money(position.notional)}</strong>
      </div>

      <div class="detail-item">
        <span>Strategia</span>
        <strong>${position.strategy_type || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Orizzonte</span>
        <strong>
          ${position.planned_horizon_sessions ?? "—"} sessioni
        </strong>
      </div>

      <div class="detail-item">
        <span>Ingresso</span>
        <strong>${formatDate(position.entry_date)}</strong>
      </div>

      <div class="detail-item">
        <span>Entry</span>
        <strong>${money(position.entry_price)}</strong>
      </div>

      <div class="detail-item">
        <span>Prezzo attuale</span>
        <strong>${money(position.mark_price)}</strong>
      </div>

      <div class="detail-item">
        <span>Prezzo aggiornato</span>
        <strong>${position.price_updated_at || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>P&amp;L</span>
        <strong class="${cls(pnl)}">
          ${money(pnl)}
        </strong>
      </div>

      <div class="detail-item">
        <span>P&amp;L %</span>
        <strong class="${cls(pnlPct)}">
          ${pct(pnlPct)}
        </strong>
      </div>

      <div class="detail-item">
        <span>Current R</span>
        <strong class="${cls(currentR)}">
          ${num(currentR)}
        </strong>
      </div>

      <div class="detail-item">
        <span>Stop</span>
        <strong>${money(position.stop)}</strong>
      </div>

      <div class="detail-item">
        <span>Target</span>
        <strong>${money(position.target)}</strong>
      </div>

      <div class="detail-item">
        <span>Giorni</span>
        <strong>${num(position.holding_days, 0)}</strong>
      </div>

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

function renderClosedDetail(position) {
  const container = document.getElementById("detailContent");

  const pnl = Number(position.realized_pnl || 0);
  const pnlPct = Number(position.realized_return || 0);

  container.innerHTML = `
    <div class="detail-grid">

      <div class="detail-item">
        <span>Ticker</span>
        <strong>${position.ticker || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Azioni</span>
        <strong>${num(position.shares, 0)}</strong>
      </div>

      <div class="detail-item">
        <span>Capitale investito</span>
        <strong>${money(position.notional)}</strong>
      </div>

      <div class="detail-item">
        <span>Strategia</span>
        <strong>${position.strategy_type || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Orizzonte</span>
        <strong>
          ${position.planned_horizon_sessions ?? "—"} sessioni
        </strong>
      </div>

      <div class="detail-item">
        <span>Rank</span>
        <strong>${position.rank ?? "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Data ingresso</span>
        <strong>${formatDate(position.entry_date)}</strong>
      </div>

      <div class="detail-item">
        <span>Entry</span>
        <strong>${money(position.entry_price)}</strong>
      </div>

      <div class="detail-item">
        <span>Exit</span>
        <strong>${money(position.exit_price)}</strong>
      </div>

      <div class="detail-item">
        <span>Realized P&amp;L</span>
        <strong class="${cls(pnl)}">
          ${money(pnl)}
        </strong>
      </div>

      <div class="detail-item">
        <span>P&amp;L %</span>
        <strong class="${cls(pnlPct)}">
          ${pct(pnlPct)}
        </strong>
      </div>

      <div class="detail-item">
        <span>Motivo chiusura</span>
        <strong>${position.close_reason || "—"}</strong>
      </div>

      <div class="detail-item">
        <span>Data uscita</span>
        <strong>${formatDate(position.exit_date)}</strong>
      </div>

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

async function loadDashboard() {
  try {
    setStatus("Aggiornamento...", true);

    const response = await fetch(
      `${DATA_URL}?t=${Date.now()}`,
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      );
    }

    const data = await response.json();

    dashboardData = data;

    renderSummary(data);
    renderOpenPositions(data.open || []);
    renderClosedPositions(data.closed || []);

    setStatus("Online", true);

  } catch (error) {

    console.error(
      "Errore caricamento dashboard:",
      error
    );

    setStatus("Errore dati", false);

    document.getElementById("openTableBody").innerHTML = `
      <tr>
        <td colspan="13" class="empty">
          Impossibile caricare i dati.
        </td>
      </tr>
    `;

    document.getElementById("closedTableBody").innerHTML = `
      <tr>
        <td colspan="9" class="empty">
          Impossibile caricare i dati.
        </td>
      </tr>
    `;
  }
}

// ------------------------------------------------------------
// Auto refresh
// ------------------------------------------------------------

loadDashboard();

setInterval(
  loadDashboard,
  60 * 1000
);