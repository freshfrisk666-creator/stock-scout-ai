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

function stockLink(ticker) {
  if (!ticker) {
    return "—";
  }

  const symbol = String(ticker).trim().toUpperCase();

  if (!symbol) {
    return "—";
  }

  const url = `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}/`;

  return `
    <a
      href="${url}"
      target="_blank"
      rel="noopener noreferrer"
      class="ticker-link"
      onclick="event.stopPropagation();"
      title="Open ${symbol} on Yahoo Finance"
    >${symbol}</a>
  `;
}

// ------------------------------------------------------------
// Status
// ------------------------------------------------------------

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
        <td>${stockLink(position.ticker)}</td>
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

// ------------------------------------------------------------
// Closed positions
// ------------------------------------------------------------

function renderClosedPositions(positions) {
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
        <td>${stockLink(position.ticker)}</td>
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

// ------------------------------------------------------------
// Open detail
// ------------------------------------------------------------

function renderOpenDetail(position) {
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

// ------------------------------------------------------------
// Closed detail
// ------------------------------------------------------------

function renderClosedDetail(position) {
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

// ------------------------------------------------------------
// Load dashboard data
// ------------------------------------------------------------

async function loadDashboard() {
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

// ------------------------------------------------------------
// Auto refresh
// ------------------------------------------------------------

loadDashboard();

setInterval(
  loadDashboard,
  60 * 1000
);
