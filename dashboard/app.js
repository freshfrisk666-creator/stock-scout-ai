const money = (v) => {
  if (v == null) return "\u2014";

  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(v);
};

const num = (v, d = 2) => {
  if (v == null || Number.isNaN(Number(v))) return "\u2014";

  return Number(v).toLocaleString("it-IT", {
    maximumFractionDigits: d,
  });
};

const pct = (v) => {
  if (v == null) return "\u2014";

  return (
    (Number(v) * 100).toLocaleString("it-IT", {
      maximumFractionDigits: 2,
    }) + "%"
  );
};

const cls = (v) => {
  if (Number(v) > 0) return "positive";
  if (Number(v) < 0) return "negative";
  return "neutral";
};

let state = null;
let isLoading = false;

function card(label, value, colorClass = "neutral") {
  return `
    <div class="card">
      <div class="label">${label}</div>
      <div class="value ${colorClass}">${value}</div>
    </div>
  `;
}

function formatDate(value) {
  if (!value) return "\u2014";

  const d = new Date(value);

  if (Number.isNaN(d.getTime())) {
    return String(value);
  }

  return d.toLocaleString("it-IT", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function setStatus(text, color = null) {
  const status = document.getElementById("status");

  if (!status) return;

  status.textContent = text;

  if (color) {
    status.style.color = color;
  }
}

function setRefreshButton(loading) {
  const button = document.getElementById("refreshBtn");

  if (!button) return;

  button.disabled = loading;

  if (loading) {
    button.textContent = "\u21bb Aggiornamento...";
  } else {
    button.textContent = "\u21bb Aggiorna";
  }
}

function render() {
  if (!state) return;

  const s = state.summary || {};

  const realizedPnl = Number(s.realized_pnl || 0);
  const unrealizedPnl = Number(s.unrealized_pnl || 0);
  const totalPnl = realizedPnl + unrealizedPnl;

  document.getElementById("summaryCards").innerHTML = [
    card("Equity", money(s.equity)),
    card("Cash", money(s.cash)),
    card("P&L aperto", money(unrealizedPnl), cls(unrealizedPnl)),
    card("P&L realizzato", money(realizedPnl), cls(realizedPnl)),
    card("P&L totale", money(totalPnl), cls(totalPnl)),
    card("Posizioni aperte", num(s.open_positions, 0)),
  ].join("");

  const latest =
    state.latest_price_at != null
      ? formatDate(state.latest_price_at)
      : "\u2014";

  document.getElementById("openMeta").textContent =
    `${s.open_positions || 0} posizioni \u2022 prezzi ${
      state.price_interval || "\u2014"
    } \u2022 ultimo dato: ${latest}`;

  document.getElementById("closedMeta").textContent =
    `${(state.closed || []).length} posizioni chiuse`;

  const openTableBody = document.querySelector("#openTable tbody");

  if (state.open && state.open.length) {
    openTableBody.innerHTML = state.open
      .map(
        (p, i) => `
          <tr data-index="${i}">
            <td>${p.rank}</td>
            <td class="ticker">${p.ticker}</td>
            <td>${num(p.entry_price)}</td>
            <td>${num(p.mark_price)}</td>
            <td class="${cls(p.unrealized_pnl)}">
              ${money(p.unrealized_pnl)}
            </td>
            <td class="${cls(p.unrealized_return)}">
              ${pct(p.unrealized_return)}
            </td>
            <td class="${cls(p.current_r)}">
              ${num(p.current_r)}R
            </td>
            <td>${num(p.stop)}</td>
            <td>${num(p.target)}</td>
            <td>${num(p.holding_days, 1)}</td>
            <td class="state ${
              Number(p.current_r) < 0 ? "negative" : "positive"
            }">
              ${Number(p.current_r) < 0 ? "WATCH" : "OPEN"}
            </td>
          </tr>
        `
      )
      .join("");
  } else {
    openTableBody.innerHTML = `
      <tr>
        <td colspan="11">Nessuna posizione aperta.</td>
      </tr>
    `;
  }

  openTableBody
    .querySelectorAll("tr[data-index]")
    .forEach((row) => {
      row.addEventListener("click", () => {
        const index = Number(row.dataset.index);
        const position = state.open[index];

        if (position) {
          showDetail(position);
        }
      });
    });

  const closedTableBody = document.querySelector("#closedTable tbody");

  if (state.closed && state.closed.length) {
    closedTableBody.innerHTML = state.closed
      .map(
        (p) => `
          <tr>
            <td class="ticker">${p.ticker}</td>
            <td>${num(p.entry_price)}</td>
            <td>${num(p.exit_price)}</td>
            <td class="${cls(p.realized_pnl)}">
              ${money(p.realized_pnl)}
            </td>
            <td class="${cls(p.realized_return)}">
              ${pct(p.realized_return)}
            </td>
            <td>${p.close_reason || "\u2014"}</td>
            <td>${formatDate(p.exit_date)}</td>
          </tr>
        `
      )
      .join("");
  } else {
    closedTableBody.innerHTML = `
      <tr>
        <td colspan="7">Nessuna posizione chiusa.</td>
      </tr>
    `;
  }

  document.getElementById("updatedAt").textContent =
    `Dashboard: ${formatDate(state.generated_at)} \u2022 Prezzi: ${latest}`;

  setStatus("\u25cf DATI AGGIORNATI", "var(--green)");
}

function showDetail(position) {
  if (!position) return;

  const signal = position.signal || {};

  const metrics = [
    ["Ticker", position.ticker],
    ["Strategy", position.strategy_type],
    [
      "Horizon",
      position.planned_horizon_sessions != null
        ? `${position.planned_horizon_sessions} sessioni`
        : "\u2014",
    ],
    ["Entry", num(position.entry_price)],
    ["Prezzo", num(position.mark_price)],
    [
      "Prezzo dato",
      position.price_updated_at
        ? formatDate(position.price_updated_at)
        : "\u2014",
    ],
    ["P&L", money(position.unrealized_pnl)],
    ["P&L %", pct(position.unrealized_return)],
    ["R attuale", `${num(position.current_r)}R`],
    ["Stop", num(position.stop)],
    ["Target", num(position.target)],
    ["Giorni", num(position.holding_days, 1)],
    ["Technical score", num(signal.technical_score)],
    ["Trend", num(signal.trend)],
    ["Momentum", num(signal.momentum)],
    ["RSI", num(signal.rsi)],
    ["Volume", num(signal.volume)],
    ["Breakout", num(signal.breakout)],
  ];

  const detailHtml = `
    <div class="detail-grid">
      ${metrics
        .map(
          ([label, value]) => `
            <div class="metric">
              <span>${label}</span>
              <strong>${value ?? "\u2014"}</strong>
            </div>
          `
        )
        .join("")}
    </div>

    <div class="signal-box">
      <h3>Snapshot del segnale di ingresso</h3>

      ${Object.entries(signal)
        .map(
          ([key, value]) => `
            <span
              style="
                display:inline-block;
                margin:3px 10px 3px 0;
                color:var(--muted);
                font-size:12px
              "
            >
              ${key}:
              <b style="color:var(--text)">
                ${value ?? "\u2014"}
              </b>
            </span>
          `
        )
        .join("")}
    </div>
  `;

  document.getElementById("detail").innerHTML = detailHtml;
}

async function load() {
  if (isLoading) return;

  isLoading = true;
  setRefreshButton(true);
  setStatus("Caricamento...");

  try {
    const response = await fetch(`data.json?ts=${Date.now()}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`data.json non disponibile: HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data || typeof data !== "object") {
      throw new Error("data.json non contiene dati validi");
    }

    state = data;

    render();
  } catch (error) {
    console.error("Errore caricamento dashboard:", error);

    setStatus("Errore aggiornamento", "var(--red)");

    const openMeta = document.getElementById("openMeta");
    if (openMeta) {
      openMeta.textContent =
        "Impossibile aggiornare i dati. Riprova tra poco.";
    }
  } finally {
    isLoading = false;
    setRefreshButton(false);
  }
}

const refreshButton = document.getElementById("refreshBtn");

if (refreshButton) {
  refreshButton.addEventListener("click", () => {
    load();
  });
}

load();

setInterval(() => {
  load();
}, 60000);