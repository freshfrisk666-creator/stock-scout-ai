const TRADE_CHART_ROOT = "trades";

let tradeChartState = {
  chart: null,
  trade: null,
  positionId: null,
};

function chartMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + " $";
}

function chartPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + "%";
}

function chartNum(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("it-IT", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function chartEl(id) {
  return document.getElementById(id);
}

function chartStatus(message, error = false) {
  const element = chartEl("tradeChartStatus");

  if (!element) {
    return;
  }

  element.textContent = message;
  element.classList.toggle("trade-chart-error", error);
}

function injectChartButtons(root) {
  if (!root) {
    return;
  }

  root.querySelectorAll("tr.position-row").forEach((row) => {
    if (row.dataset.chartReady === "1") {
      return;
    }

    const positionId = row.dataset.id;

    if (!positionId) {
      return;
    }

    const cell = document.createElement("td");
    cell.innerHTML =
      '<button type="button" class="chart-btn">📊 Chart</button>';

    const button = cell.querySelector("button");

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openTradeChart(positionId);
    });

    row.appendChild(cell);
    row.dataset.chartReady = "1";
  });
}

function observeTable(root) {
  if (!root) {
    return;
  }

  injectChartButtons(root);

  const observer = new MutationObserver(() => {
    injectChartButtons(root);
  });

  observer.observe(root, {
    childList: true,
    subtree: true,
  });
}

function openTradeChart(positionId) {
  const modal = chartEl("tradeChartModal");

  if (!modal) {
    return;
  }

  modal.hidden = false;
  document.body.classList.add("modal-open");

  tradeChartState.positionId = Number(positionId);

  chartStatus("Caricamento del tracciato...");

  fetchTradeData(positionId);
}

async function fetchTradeData(positionId) {
  try {
    const response = await fetch(
      TRADE_CHART_ROOT +
      "/" +
      encodeURIComponent(positionId) +
      ".json?t=" +
      Date.now(),
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const trade = await response.json();

    if (trade.error) {
      throw new Error(trade.error);
    }

    tradeChartState.trade = trade;

    renderTradeHeader(trade);
    renderTradeContext(trade);
    drawTradeChart(trade);

    chartStatus(
      "Tracciato aggiornato: " +
      new Date().toLocaleString("it-IT")
    );
  } catch (error) {
    destroyTradeChart();
    chartStatus(
      "Errore caricamento chart: " + error.message,
      true
    );
  }
}

function renderTradeHeader(trade) {
  const title = chartEl("tradeChartTitle");
  const subtitle = chartEl("tradeChartSubtitle");

  title.textContent =
    trade.ticker + " — " + (trade.strategy_type || "SWING");

  subtitle.textContent =
    "Entry " +
    chartMoney(trade.entry_price) +
    " · " +
    (trade.status === "CLOSED"
      ? "Trade chiuso"
      : "Posizione aperta");
}

function renderTradeContext(trade) {
  const container = chartEl("tradeChartContext");
  const signal = trade.signal || {};
  const vix = trade.vix_context || {};

  const pnlClass =
    Number(trade.realized_pnl) > 0
      ? "positive"
      : Number(trade.realized_pnl) < 0
        ? "negative"
        : "";

  const returnClass =
    Number(trade.realized_return_pct) > 0
      ? "positive"
      : Number(trade.realized_return_pct) < 0
        ? "negative"
        : "";

  container.innerHTML = `
    <div class="trade-context-grid">
      <div class="trade-context-card"><span>Technical Score</span><strong>${chartNum(signal.technical_score)}</strong></div>
      <div class="trade-context-card"><span>Trend</span><strong>${chartNum(signal.trend_score)}</strong></div>
      <div class="trade-context-card"><span>Momentum</span><strong>${chartNum(signal.momentum_score)}</strong></div>
      <div class="trade-context-card"><span>RSI</span><strong>${chartNum(signal.rsi_score)}</strong></div>
      <div class="trade-context-card"><span>Volume</span><strong>${chartNum(signal.volume_score)}</strong></div>
      <div class="trade-context-card"><span>Breakout</span><strong>${chartNum(signal.breakout_score)}</strong></div>
      <div class="trade-context-card"><span>Risk / Reward</span><strong>${chartNum(signal.risk_reward)}</strong></div>

      <div class="trade-context-card"><span>VIX at entry</span><strong>${chartNum(vix.entry)}</strong></div>
      <div class="trade-context-card"><span>VIX media trade</span><strong>${chartNum(vix.average)}</strong></div>
      <div class="trade-context-card"><span>VIX uscita</span><strong>${chartNum(vix.exit)}</strong></div>
      <div class="trade-context-card"><span>VIX 5 giorni</span><strong>${chartPct(vix.change_5d_pct)}</strong></div>
      <div class="trade-context-card"><span>VIX 20 giorni</span><strong>${chartPct(vix.change_20d_pct)}</strong></div>
    </div>

    <div class="trade-plan-grid">
      <div><span>Entry</span><strong>${chartMoney(trade.entry_price)}</strong></div>
      <div><span>Stop</span><strong>${chartMoney(trade.stop)}</strong></div>
      <div><span>Target</span><strong>${chartMoney(trade.target)}</strong></div>
      <div><span>Exit</span><strong>${chartMoney(trade.exit_price)}</strong></div>
      <div><span>Risultato</span><strong class="${pnlClass}">${chartMoney(trade.realized_pnl)}</strong></div>
      <div><span>Return</span><strong class="${returnClass}">${chartPct(trade.realized_return_pct)}</strong></div>
    </div>

    <div class="trade-chart-note">
      Il VIX è usato solo come contesto del mercato. Non viene disegnato nel chart e non modifica lo scoring.
    </div>
  `;
}

function barSeriesData(bars, key) {
  return bars
    .filter((bar) => bar[key] !== null && bar[key] !== undefined)
    .map((bar) => ({
      time: bar.time,
      value: Number(bar[key]),
    }));
}

function destroyTradeChart() {
  if (tradeChartState.chart) {
    tradeChartState.chart.remove();
    tradeChartState.chart = null;
  }

  const canvas = chartEl("tradeChartCanvas");

  if (canvas) {
    canvas.innerHTML = "";
  }
}

function addPriceLine(series, price, title, color, lineStyle) {
  if (
    price === null ||
    price === undefined ||
    Number.isNaN(Number(price))
  ) {
    return;
  }

  series.createPriceLine({
    price: Number(price),
    color,
    lineWidth: 1,
    lineStyle,
    axisLabelVisible: true,
    title,
  });
}

function drawTradeChart(trade) {
  destroyTradeChart();

  if (!window.LightweightCharts) {
    chartStatus(
      "Libreria grafica non disponibile.",
      true
    );
    return;
  }

  if (!trade.bars || trade.bars.length === 0) {
    chartStatus(
      "Dati storici non disponibili.",
      true
    );
    return;
  }

  const {
    createChart,
    CandlestickSeries,
    LineSeries,
    HistogramSeries,
    LineStyle,
  } = window.LightweightCharts;

  const container = chartEl("tradeChartCanvas");

  const chart = createChart(container, {
    autoSize: true,
    layout: {
      background: { color: "#0b0f14" },
      textColor: "#9aa6b2",
      attributionLogo: true,
    },
    grid: {
      vertLines: { color: "rgba(141,153,168,0.10)" },
      horzLines: { color: "rgba(141,153,168,0.10)" },
    },
    crosshair: {
      mode: 0,
    },
    rightPriceScale: {
      borderColor: "#26303d",
    },
    timeScale: {
      borderColor: "#26303d",
      timeVisible: false,
      secondsVisible: false,
    },
    handleScroll: true,
    handleScale: true,
  });

  tradeChartState.chart = chart;

  const candles = chart.addSeries(CandlestickSeries, {
    upColor: "#35c98b",
    downColor: "#ff647c",
    borderUpColor: "#35c98b",
    borderDownColor: "#ff647c",
    wickUpColor: "#35c98b",
    wickDownColor: "#ff647c",
    priceLineVisible: false,
  });

  candles.setData(
    trade.bars.map((bar) => ({
      time: bar.time,
      open: Number(bar.open),
      high: Number(bar.high),
      low: Number(bar.low),
      close: Number(bar.close),
    }))
  );

  const maConfig = [
    ["sma20", "SMA20", "#f0c36a", 1],
    ["sma50", "SMA50", "#6ea8fe", 1],
    ["sma200", "SMA200", "#c084fc", 2],
  ];

  maConfig.forEach(([key, title, color, width]) => {
    const line = chart.addSeries(LineSeries, {
      color,
      lineWidth: width,
      priceLineVisible: false,
      lastValueVisible: false,
      title,
    });

    line.setData(
      barSeriesData(trade.bars, key)
    );
  });

  addPriceLine(
    candles,
    trade.entry_price,
    "ENTRY",
    "#6ea8fe",
    LineStyle.Dashed
  );

  addPriceLine(
    candles,
    trade.stop,
    "STOP",
    "#ff647c",
    LineStyle.Dashed
  );

  addPriceLine(
    candles,
    trade.target,
    "TARGET",
    "#35c98b",
    LineStyle.Dashed
  );

  if (trade.exit_price !== null && trade.exit_price !== undefined) {
    addPriceLine(
      candles,
      trade.exit_price,
      "EXIT",
      "#f0c36a",
      LineStyle.Dotted
    );
  }

  (trade.levels || []).forEach((level) => {
    addPriceLine(
      candles,
      level.price,
      level.kind === "support" ? "SUPPORT" : "RESISTANCE",
      level.kind === "support"
        ? "rgba(53,201,139,0.55)"
        : "rgba(255,100,124,0.55)",
      LineStyle.Dotted
    );
  });

  (trade.trendlines || []).forEach((trendline) => {
    const line = chart.addSeries(LineSeries, {
      color:
        trendline.kind === "support"
          ? "rgba(53,201,139,0.85)"
          : "rgba(110,168,254,0.85)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      title:
        trendline.kind === "support"
          ? "Support trendline"
          : "Resistance trendline",
    });

    line.setData([
      {
        time: trendline.start.time,
        value: Number(trendline.start.price),
      },
      {
        time: trendline.end.time,
        value: Number(trendline.end.price),
      },
    ]);
  });

  const volume = chart.addSeries(HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "",
    color: "rgba(110,168,254,0.30)",
  }, 1);

  volume.priceScale().applyOptions({
    scaleMargins: {
      top: 0.82,
      bottom: 0,
    },
  });

  volume.setData(
    trade.bars
      .filter((bar) => bar.volume !== null && bar.volume !== undefined)
      .map((bar) => ({
        time: bar.time,
        value: Number(bar.volume),
        color:
          Number(bar.close) >= Number(bar.open)
            ? "rgba(53,201,139,0.35)"
            : "rgba(255,100,124,0.35)",
      }))
  );

  chart.timeScale().fitContent();
}

function closeTradeChart() {
  destroyTradeChart();

  const modal = chartEl("tradeChartModal");

  if (modal) {
    modal.hidden = true;
  }

  document.body.classList.remove("modal-open");

  tradeChartState.trade = null;
  tradeChartState.positionId = null;
}

function refreshTradeChart() {
  if (tradeChartState.positionId === null) {
    return;
  }

  chartStatus("Aggiornamento del tracciato...");
  fetchTradeData(tradeChartState.positionId);
}

function downloadTradeChartPng() {
  if (!tradeChartState.chart) {
    return;
  }

  const canvas = tradeChartState.chart.takeScreenshot();
  const link = document.createElement("a");

  link.download =
    "stock-scout-" +
    (tradeChartState.trade?.ticker || "trade") +
    "-chart.png";

  link.href = canvas.toDataURL("image/png");
  link.click();
}

function downloadTradeChartCsv() {
  const trade = tradeChartState.trade;

  if (!trade || !Array.isArray(trade.bars)) {
    return;
  }

  const headers = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "sma20",
    "sma50",
    "sma200",
    "rsi14",
    "atr14",
    "volume_ratio",
    "breakout_strength_20d",
  ];

  const lines = [headers.join(",")];

  trade.bars.forEach((bar) => {
    lines.push(
      headers.map((key) => {
        const value = bar[key];

        if (value === null || value === undefined) {
          return "";
        }

        return String(value).replace(/"/g, '""');
      }).join(",")
    );
  });

  const blob = new Blob(
    [lines.join("\n")],
    { type: "text/csv;charset=utf-8" }
  );

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download =
    "stock-scout-" +
    (trade.ticker || "trade") +
    "-data.csv";

  document.body.appendChild(link);
  link.click();
  link.remove();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeTradeChart();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  observeTable(document.getElementById("openTableBody"));
  observeTable(document.getElementById("closedTableBody"));
});

window.openTradeChart = openTradeChart;
window.closeTradeChart = closeTradeChart;
window.refreshTradeChart = refreshTradeChart;
window.downloadTradeChartPng = downloadTradeChartPng;
window.downloadTradeChartCsv = downloadTradeChartCsv;
