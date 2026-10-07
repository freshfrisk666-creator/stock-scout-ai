const money = (v) => {
  if (v == null) return "\u2014";

  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(v);
};

const num = (v, d = 2) => {
  if (v == null || Number.isNaN(Number(v))) {
    return "\u2014";
  }

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

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString("it-IT", {
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

  button.textContent = loading
    ? "\u21bb Aggiornamento..."
    : "\u21bb Aggiorna";
}

function render() {
  if (!state) return;

  const summary = state.summary || {};

  const realizedPnl =
    Number(summary.realized_pnl || 0);

  const unrealizedPnl =
    Number(summary.unrealized_pnl || 0);

  const totalPnl =
    realizedPnl + unrealizedPnl;

  document.getElementById(
    "summaryCards"
  ).innerHTML = [
    card("Equity", money(summary.equity)),
    card("Cash", money(summary.cash)),
    card(
      "P&L aperto",
      money(unrealizedPnl),
      cls(unrealizedPnl)
    ),
    card(
      "P&L realizzato",
      money(realizedPnl),
      cls(realizedPnl)
    ),
    card(
      "P&L totale",
      money(totalPnl),
      cls(totalPnl)
    ),
    card(
      "Posizioni aperte",
      num(summary.open_positions, 0)
    ),
  ].join("");

  const latest =
    state.latest_price_at
      ? formatDate(state.latest_price_at)
      : "\u2014";

  document.getElementById(
    "openMeta"
  ).textContent =
    `${summary.open_positions || 0} posizioni \u2022 prezzi ${
      state.price_interval || "\u2014"
    } \u2022 ultimo dato: ${latest}`;

  document.getElementById(
    "closedMeta"
  ).textContent =
    `${(state.closed || []).length} posizioni chiuse`;

  // ---------------------------------------------------------
  // OPEN TABLE
  // ---------------------------------------------------------

  const openTableBody =
    document.querySelector("#openTable tbody");

  if (state.open && state.open.length) {
    openTableBody.innerHTML = state.open
      .map(
        (position, index) => `
          <tr data-open-index="${index}">
            <td>${position.rank}</td>

            <td class="ticker">
              ${position.ticker}
            </td>

            <td>
              ${num(position.entry_price)}
            </td>

            <td>
              ${num(position.mark_price)}
            </td>

            <td class="${cls(position.unrealized_pnl)}">
              ${money(position.unrealized_pnl)}
            </td>

            <td class="${cls(position.unrealized_return)}">
              ${pct(position.unrealized_return)}
            </td>

            <td class="${cls(position.current_r)}">
              ${num(position.current_r)}R
            </td>

            <td>
              ${num(position.stop)}
            </td>

            <td>
              ${num(position.target)}
            </td>

            <td>
              ${num(position.holding_days, 1)}
            </td>

            <td class="state ${
              Number(position.current_r) < 0
                ? "negative"
                : "positive"
            }">
              ${
                Number(position.current_r) < 0
                  ? "WATCH"
                  : "OPEN"
              }
            </td>
          </tr>
        `
      )
      .join("");
  } else {
    openTableBody.innerHTML = `
      <tr>
        <td colspan="11">
          Nessuna posizione aperta.
        </td>
      </tr>
    `;
  }

  openTableBody
    .querySelectorAll(
      "tr[data-open-index]"
    )
    .forEach((row) => {
      row.addEventListener("click", () => {
        const index =
          Number(row.dataset.openIndex);

        const position =
          state.open[index];

        if (position) {
          showOpenDetail(position);
        }
      });
    });

  // ---------------------------------------------------------
  // CLOSED TABLE
  // ---------------------------------------------------------

  const closedTableBody =
    document.querySelector("#closedTable tbody");

  if (state.closed && state.closed.length) {
    closedTableBody.innerHTML =
      state.closed
        .map(
          (position, index) => `
            <tr data-closed-index="${index}">
              <td class="ticker">
                ${position.ticker}
              </td>

              <td>
                ${num(position.entry_price)}
              </td>

              <td>
                ${num(position.exit_price)}
              </td>

              <td class="${cls(position.realized_pnl)}">
                ${money(position.realized_pnl)}
              </td>

              <td class="${cls(position.realized_return)}">
                ${pct(position.realized_return)}
              </td>

              <td>
                ${position.close_reason || "\u2014"}
              </td>

              <td>
                ${formatDate(position.exit_date)}
              </td>
            </tr>
          `
        )
        .join("");
  } else {
    closedTableBody.innerHTML = `
      <tr>
        <td colspan="7">
          Nessuna posizione chiusa.
        </td>
      </tr>
    `;
  }

  closedTableBody
    .querySelectorAll(
      "tr[data-closed-index]"
    )
    .forEach((row) => {
      row.addEventListener("click", () => {
        const index =
          Number(row.dataset.closedIndex);

        const position =
          state.closed[index];

        if (position) {
          showClosedDetail(position);
        }
      });
    });

  document.getElementById(
    "updatedAt"
  ).textContent =
    `Dashboard: ${formatDate(
      state.generated_at
    )} \u2022 Prezzi: ${latest}`;

  setStatus(
    "\u25cf DATI AGGIORNATI",
    "var(--green)"
  );
}

function buildSignalMetrics(signal) {
  return [
    [
      "Technical score",
      num(signal.technical_score),
    ],
    [
      "Trend",
      num(signal.trend_score),
    ],
    [
      "Momentum",
      num(signal.momentum_score),
    ],
    [
      "RSI",
      num(signal.rsi_score),
    ],
    [
      "Volume",
      num(signal.volume_score),
    ],
    [
      "Breakout",
      num(signal.breakout_score),
    ],
    [
      "Risk / Reward",
      num(signal.risk_reward),
    ],
  ];
}

function buildSignalBox(signal) {
  return `
    <div class="signal-box">
      <h3>
        Snapshot del segnale di ingresso
      </h3>

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
}

function renderDetail(metrics, signal) {
  document.getElementById(
    "detail"
  ).innerHTML = `
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

    ${buildSignalBox(signal)}
  `;
}

function showOpenDetail(position) {
  const signal =
    position.signal || {};

  const metrics = [
    ["Ticker", position.ticker],

    [
      "Strategy",
      position.strategy_type,
    ],

    [
      "Horizon",
      position.planned_horizon_sessions != null
        ? `${position.planned_horizon_sessions} sessioni`
        : "\u2014",
    ],

    [
      "Entry",
      num(position.entry_price),
    ],

    [
      "Prezzo",
      num(position.mark_price),
    ],

    [
      "Prezzo dato",
      position.price_updated_at
        ? formatDate(position.price_updated_at)
        : "\u2014",
    ],

    [
      "P&L",
      money(position.unrealized_pnl),
    ],

    [
      "P&L %",
      pct(position.unrealized_return),
    ],

    [
      "R attuale",
      `${num(position.current_r)}R`,
    ],

    [
      "Stop",
      num(position.stop),
    ],

    [
      "Target",
      num(position.target),
    ],

    [
      "Giorni",
      num(position.holding_days, 1),
    ],

    ...buildSignalMetrics(signal),
  ];

  renderDetail(metrics, signal);
}

function showClosedDetail(position) {
  const signal =
    position.signal || {};

  const metrics = [
    ["Ticker", position.ticker],

    [
      "Strategy",
      position.strategy_type,
    ],

    [
      "Horizon",
      position.planned_horizon_sessions != null
        ? `${position.planned_horizon_sessions} sessioni`
        : "\u2014",
    ],

    [
      "Rank ingresso",
      position.rank != null
        ? num(position.rank, 0)
        : "\u2014",
    ],

    [
      "Data ingresso",
      formatDate(position.entry_date),
    ],

    [
      "Entry",
      num(position.entry_price),
    ],

    [
      "Exit",
      num(position.exit_price),
    ],

    [
      "P&L realizzato",
      money(position.realized_pnl),
    ],

    [
      "P&L %",
      pct(position.realized_return),
    ],

    [
      "Motivo",
      position.close_reason || "\u2014",
    ],

    [
      "Data uscita",
      formatDate(position.exit_date),
    ],

    ...buildSignalMetrics(signal),
  ];

  renderDetail(metrics, signal);
}

async function load() {
  if (isLoading) return;

  isLoading = true;

  setRefreshButton(true);
  setStatus("Caricamento...");

  try {
    const response = await fetch(
      `data.json?ts=${Date.now()}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        `data.json non disponibile: HTTP ${response.status}`
      );
    }

    const data =
      await response.json();

    if (
      !data ||
      typeof data !== "object"
    ) {
      throw new Error(
        "data.json non contiene dati validi"
      );
    }

    state = data;

    render();
  } catch (error) {
    console.error(
      "Errore caricamento dashboard:",
      error
    );

    setStatus(
      "Errore aggiornamento",
      "var(--red)"
    );
  } finally {
    isLoading = false;

    setRefreshButton(false);
  }
}

const refreshButton =
  document.getElementById("refreshBtn");

if (refreshButton) {
  refreshButton.addEventListener(
    "click",
    () => {
      load();
    }
  );
}

load();

setInterval(
  () => {
    load();
  },
  60000
);