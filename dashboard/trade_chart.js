const TRADE_CHART_ROOT = "trades";

let tradeChartState = {
  chart: null,
  trade: null,
  positionId: null,
  candles: null,
  rsiMarkers: null,
};

function chartMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " $";
}

function chartPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function chartNum(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("it-IT", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function chartEl(id) { return document.getElementById(id); }

function chartStatus(message, error = false) {
  const element = chartEl("tradeChartStatus");
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("trade-chart-error", error);
}

function injectChartButtons(root) {
  if (!root) return;
  root.querySelectorAll("tr.position-row").forEach((row) => {
    if (row.dataset.chartReady === "1") return;
    const positionId = row.dataset.id;
    if (!positionId) return;

    const cell = document.createElement("td");
    cell.innerHTML = '<button type="button" class="chart-btn">📊 Chart</button>';
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
  if (!root) return;
  injectChartButtons(root);
  const observer = new MutationObserver(() => injectChartButtons(root));
  observer.observe(root, { childList: true, subtree: true });
}

function openTradeChart(positionId) {
  const modal = chartEl("tradeChartModal");
  if (!modal) return;
  modal.hidden = false;
  document.body.classList.add("modal-open");
  tradeChartState.positionId = Number(positionId);
  chartStatus("Caricamento del tracciato...");
  fetchTradeData(positionId);
}

async function fetchTradeData(positionId) {
  try {
    const response = await fetch(
      TRADE_CHART_ROOT + "/" + encodeURIComponent(positionId) + ".json?t=" + Date.now(),
      { cache: "no-store" }
    );
    if (!response.ok) throw new Error("HTTP " + response.status);
    const trade = await response.json();
    if (trade.error) throw new Error(trade.error);

    tradeChartState.trade = trade;
    renderTradeHeader(trade);
    renderTradeContext(trade);
    drawTradeChart(trade);

    chartStatus("Tracciato aggiornato: " + new Date().toLocaleString("it-IT"));
  } catch (error) {
    destroyTradeChart();
    chartStatus("Errore caricamento chart: " + error.message, true);
  }
}

function renderTradeHeader(trade) {
  chartEl("tradeChartTitle").textContent = trade.ticker + " — " + (trade.strategy_type || "SWING");
  chartEl("tradeChartSubtitle").textContent =
    "Entry " + chartMoney(trade.entry_price) + " · " +
    (trade.status === "CLOSED" ? "Trade chiuso" : "Posizione aperta");
}

function renderTradeContext(trade) {
  const container = chartEl("tradeChartContext");
  const signal = trade.signal || {};
  const vix = trade.vix_context || {};
  const divergences = trade.divergences || [];
  const bullish = divergences.filter((item) => item.type === "bullish");
  const bearish = divergences.filter((item) => item.type === "bearish");

  const pnlClass = Number(trade.realized_pnl) > 0 ? "positive" : Number(trade.realized_pnl) < 0 ? "negative" : "";
  const returnClass = Number(trade.realized_return_pct) > 0 ? "positive" : Number(trade.realized_return_pct) < 0 ? "negative" : "";

  let divergenceLabel = "Nessuna divergenza RSI significativa";
  let divergenceClass = "neutral";
  if (bullish.length && bearish.length) {
    divergenceLabel = "Bullish + Bearish divergence";
    divergenceClass = "mixed";
  } else if (bullish.length) {
    divergenceLabel = "Bullish divergence presente";
    divergenceClass = "bullish";
  } else if (bearish.length) {
    divergenceLabel = "Bearish divergence presente";
    divergenceClass = "bearish";
  }

  container.innerHTML = `
    <div class="trade-divergence-banner ${divergenceClass}">
      <div>
        <span>Bottom analysis</span>
        <strong>${divergenceLabel}</strong>
      </div>
      <small>RSI14 · ${bullish.length} bullish · ${bearish.length} bearish</small>
    </div>

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
      <div><span>Entry</span><strong class="plan-entry">${chartMoney(trade.entry_price)}</strong></div>
      <div><span>Stop</span><strong class="plan-stop">${chartMoney(trade.stop)}</strong></div>
      <div><span>Target</span><strong class="plan-target">${chartMoney(trade.target)}</strong></div>
      <div><span>Exit</span><strong>${chartMoney(trade.exit_price)}</strong></div>
      <div><span>Risultato</span><strong class="${pnlClass}">${chartMoney(trade.realized_pnl)}</strong></div>
      <div><span>Return</span><strong class="${returnClass}">${chartPct(trade.realized_return_pct)}</strong></div>
    </div>

    <div class="trade-chart-note">
      Il VIX è usato solo come contesto del mercato. Non viene disegnato nel chart e non modifica lo scoring. Le divergenze sono rilevate su prezzo + RSI14 e sono un'analisi diagnostica, non un segnale automatico.
    </div>
  `;
}

function barSeriesData(bars, key) {
  return bars.filter((bar) => bar[key] !== null && bar[key] !== undefined).map((bar) => ({ time: bar.time, value: Number(bar[key]) }));
}

function destroyTradeChart() {
  if (tradeChartState.chart) {
    tradeChartState.chart.remove();
    tradeChartState.chart = null;
  }
  tradeChartState.candles = null;
  tradeChartState.rsiMarkers = null;
  const canvas = chartEl("tradeChartCanvas");
  if (canvas) canvas.innerHTML = "";
}

function addPriceLine(series, price, title, color, lineStyle, lineWidth = 1) {
  if (price === null || price === undefined || Number.isNaN(Number(price))) return;
  series.createPriceLine({
    price: Number(price),
    color,
    lineWidth,
    lineStyle,
    axisLabelVisible: true,
    title,
  });
}

class PriceZonePrimitive {
  constructor(chart, series, zones) {
    this.chart = chart;
    this.series = series;
    this.zones = zones || [];
  }

  attached() {}
  detached() {}
  updateAllViews() {}

  zoneStyle(zone) {
    switch (zone.kind) {
      case "trade_reward":
        return { fill: "rgba(53, 201, 139, 0.11)", stroke: "rgba(53, 201, 139, 0.34)", text: "rgba(91, 227, 168, 0.95)" };
      case "trade_risk":
        return { fill: "rgba(255, 84, 108, 0.10)", stroke: "rgba(255, 84, 108, 0.34)", text: "rgba(255, 126, 144, 0.95)" };
      case "support":
        return { fill: "rgba(62, 174, 255, 0.14)", stroke: "rgba(62, 174, 255, 0.42)", text: "rgba(112, 201, 255, 0.98)" };
      case "resistance":
        return { fill: "rgba(240, 178, 74, 0.10)", stroke: "rgba(240, 178, 74, 0.34)", text: "rgba(255, 205, 110, 0.98)" };
      default:
        return { fill: "rgba(141, 153, 168, 0.05)", stroke: "rgba(141, 153, 168, 0.20)", text: "rgba(200, 208, 218, 0.90)" };
    }
  }

  paneViews() {
    return [{
      zOrder: () => "bottom",
      renderer: () => ({
        draw: (target) => {
          target.useMediaCoordinateSpace((scope) => {
            const ctx = scope.context;
            const width = scope.mediaSize.width;

            for (const zone of this.zones) {
              const startX = this.chart.timeScale().timeToCoordinate(zone.start_time);
              const endX = this.chart.timeScale().timeToCoordinate(zone.end_time);
              if (startX === null && endX === null) continue;

              const x1 = startX === null ? 0 : startX;
              const x2 = endX === null ? width : endX;
              const left = Math.max(0, Math.min(width, Math.min(x1, x2)));
              const right = Math.max(0, Math.min(width, Math.max(x1, x2)));

              const yTop = this.series.priceToCoordinate(Number(zone.high));
              const yBottom = this.series.priceToCoordinate(Number(zone.low));
              if (yTop === null || yBottom === null) continue;

              const top = Math.min(yTop, yBottom);
              const height = Math.max(2, Math.abs(yBottom - yTop));
              const style = this.zoneStyle(zone);

              ctx.save();
              ctx.fillStyle = style.fill;
              ctx.fillRect(left, top, Math.max(1, right - left), height);

              ctx.strokeStyle = style.stroke;
              ctx.lineWidth = zone.kind === "support" ? 1.5 : 1;
              ctx.strokeRect(left + 0.5, top + 0.5, Math.max(1, right - left - 1), Math.max(1, height - 1));

              if (zone.label && right - left > 90 && height >= 16) {
                ctx.font = "600 11px Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
                ctx.fillStyle = style.text;
                ctx.textAlign = "right";
                ctx.textBaseline = "middle";
                ctx.fillText(zone.label, right - 8, top + Math.min(height - 7, 15));
              }
              ctx.restore();
            }
          });
        },
      }),
    }];
  }
}

function attachZonePrimitive(chart, series, zones, bars, trade) {
  if (!bars || bars.length < 2) return;

  const allZones = [...(zones || [])];
  const entryTime = Number(trade?.entry_time || bars[0].time);
  const tradeEndTime = Number(trade?.trade_end_time || bars[bars.length - 1].time);

  if (Number.isFinite(Number(trade?.entry_price)) && Number.isFinite(Number(trade?.target))) {
    allZones.push({
      kind: "trade_reward",
      low: Math.min(Number(trade.entry_price), Number(trade.target)),
      high: Math.max(Number(trade.entry_price), Number(trade.target)),
      start_time: entryTime,
      end_time: tradeEndTime,
      label: "TARGET / REWARD",
    });
  }

  if (Number.isFinite(Number(trade?.entry_price)) && Number.isFinite(Number(trade?.stop))) {
    allZones.push({
      kind: "trade_risk",
      low: Math.min(Number(trade.stop), Number(trade.entry_price)),
      high: Math.max(Number(trade.stop), Number(trade.entry_price)),
      start_time: entryTime,
      end_time: tradeEndTime,
      label: "STOP / RISK",
    });
  }

  const enriched = allZones.map((zone) => ({
    ...zone,
    start_time: zone.start_time ?? bars[0].time,
    end_time: zone.end_time ?? bars[bars.length - 1].time,
  }));

  if (enriched.length > 0) {
    series.attachPrimitive(new PriceZonePrimitive(chart, series, enriched));
  }
}

function buildDivergenceSeries(chart, rsiSeries, divergences) {
  const markers = [];
  const lineSeries = [];

  divergences.forEach((divergence, index) => {
    const bullish = divergence.type === "bullish";
    const color = bullish ? "#35c98b" : "#ff647c";
    const position = bullish ? "belowBar" : "aboveBar";
    const shape = bullish ? "arrowUp" : "arrowDown";
    const text = bullish ? "BULL" : "BEAR";

    markers.push({
      time: divergence.start_time,
      position,
      color,
      shape: "circle",
      text: "D1",
      size: 1,
    });
    markers.push({
      time: divergence.end_time,
      position,
      color,
      shape,
      text,
      size: 1.5,
    });

    const line = chart.addSeries(window.LightweightCharts.LineSeries, {
      color,
      lineWidth: 2,
      lineStyle: window.LightweightCharts.LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      title: bullish ? "Bullish divergence" : "Bearish divergence",
    }, 1);
    line.setData([
      { time: divergence.start_time, value: Number(divergence.start_rsi) },
      { time: divergence.end_time, value: Number(divergence.end_rsi) },
    ]);
    lineSeries.push(line);
  });

  if (window.LightweightCharts.createSeriesMarkers) {
    tradeChartState.rsiMarkers = window.LightweightCharts.createSeriesMarkers(rsiSeries, markers);
  }
  return lineSeries;
}

function drawTradeChart(trade) {
  destroyTradeChart();

  if (!window.LightweightCharts) {
    chartStatus("Libreria grafica non disponibile.", true);
    return;
  }
  if (!trade.bars || trade.bars.length === 0) {
    chartStatus("Dati storici non disponibili.", true);
    return;
  }

  const {
    createChart,
    CandlestickSeries,
    LineSeries,
    LineStyle,
  } = window.LightweightCharts;

  const container = chartEl("tradeChartCanvas");

  const chart = createChart(container, {
    autoSize: true,
    layout: {
      background: { color: "#0b0f14" },
      textColor: "#9aa6b2",
      attributionLogo: true,
      panes: {
        separatorColor: "#26303d",
        separatorHoverColor: "#3b4a5d",
        enableResize: true,
      },
    },
    grid: {
      vertLines: { color: "rgba(141,153,168,0.08)" },
      horzLines: { color: "rgba(141,153,168,0.08)" },
    },
    crosshair: { mode: 0 },
    rightPriceScale: { borderColor: "#26303d" },
    timeScale: { borderColor: "#26303d", timeVisible: false, secondsVisible: false },
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
  tradeChartState.candles = candles;

  candles.setData(trade.bars.map((bar) => ({
    time: bar.time,
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
  })));

  const maConfig = [
    ["sma20", "SMA20", "rgba(240,195,106,0.60)", 1],
    ["sma50", "SMA50", "rgba(110,168,254,0.52)", 1],
    ["sma200", "SMA200", "rgba(169,120,214,0.42)", 1],
  ];
  maConfig.forEach(([key, title, color, width]) => {
    const line = chart.addSeries(LineSeries, {
      color,
      lineWidth: width,
      priceLineVisible: false,
      lastValueVisible: false,
      title,
    });
    line.setData(barSeriesData(trade.bars, key));
  });

  // Trade-plan levels are intentionally dominant. The colored bands below make
  // the reward/risk structure immediately readable without hiding the candles.
  addPriceLine(candles, trade.entry_price, "ENTRY", "#76b7ff", LineStyle.Solid, 4);
  addPriceLine(candles, trade.stop, "STOP LOSS", "#ff4f6d", LineStyle.Solid, 4);
  addPriceLine(candles, trade.target, "TARGET", "#2fe39a", LineStyle.Solid, 4);

  if (trade.exit_price !== null && trade.exit_price !== undefined) {
    addPriceLine(candles, trade.exit_price, "EXIT", "#ffd166", LineStyle.Solid, 3);
  }

  attachZonePrimitive(chart, candles, trade.zones || [], trade.bars, trade);

  (trade.trendlines || []).forEach((trendline) => {
    const line = chart.addSeries(LineSeries, {
      color: trendline.kind === "support" ? "rgba(62,174,255,0.48)" : "rgba(240,178,74,0.42)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      title: trendline.kind === "support" ? "Support trendline" : "Resistance trendline",
    });
    line.setData([
      { time: trendline.start.time, value: Number(trendline.start.price) },
      { time: trendline.end.time, value: Number(trendline.end.price) },
    ]);
  });

  // Bottom pane: RSI14 + divergence analysis. Volume is intentionally omitted from
  // the visual chart to keep the trade review readable; it remains in the CSV export.
  const rsi = chart.addSeries(LineSeries, {
    color: "#d0a7ff",
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
    title: "RSI14",
    priceScaleId: "rsi",
  }, 1);
  rsi.setData(barSeriesData(trade.bars, "rsi14"));

  addPriceLine(rsi, 70, "70", "rgba(255,100,124,0.55)", LineStyle.Dashed, 1);
  addPriceLine(rsi, 50, "50", "rgba(154,166,178,0.28)", LineStyle.Dotted, 1);
  addPriceLine(rsi, 30, "30", "rgba(53,201,139,0.55)", LineStyle.Dashed, 1);

  const rsiPane = chart.panes()[1];
  if (rsiPane) {
    rsiPane.setHeight(155);
  }

  buildDivergenceSeries(chart, rsi, trade.divergences || []);

  chart.timeScale().fitContent();
}

function closeTradeChart() {
  destroyTradeChart();
  const modal = chartEl("tradeChartModal");
  if (modal) modal.hidden = true;
  document.body.classList.remove("modal-open");
  tradeChartState.trade = null;
  tradeChartState.positionId = null;
}

function refreshTradeChart() {
  if (tradeChartState.positionId === null) return;
  chartStatus("Aggiornamento del tracciato...");
  fetchTradeData(tradeChartState.positionId);
}

function downloadTradeChartPng() {
  if (!tradeChartState.chart) return;
  const canvas = tradeChartState.chart.takeScreenshot();
  const link = document.createElement("a");
  link.download = "stock-scout-" + (tradeChartState.trade?.ticker || "trade") + "-chart.png";
  link.href = canvas.toDataURL("image/png");
  link.click();
}

function downloadTradeChartCsv() {
  const trade = tradeChartState.trade;
  if (!trade || !Array.isArray(trade.bars)) return;

  const headers = [
    "date", "open", "high", "low", "close", "volume",
    "sma20", "sma50", "sma200", "rsi14", "atr14", "volume_ratio", "breakout_strength_20d",
  ];
  const lines = [headers.join(",")];
  trade.bars.forEach((bar) => {
    lines.push(headers.map((key) => {
      const value = bar[key];
      if (value === null || value === undefined) return "";
      return String(value).replace(/"/g, '""');
    }).join(","));
  });

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "stock-scout-" + (trade.ticker || "trade") + "-data.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeTradeChart();
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
