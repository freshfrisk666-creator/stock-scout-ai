const TRADE_CHART_ROOT = "trades";

let tradeChartState = {
  chart: null,
  trade: null,
  positionId: null,
  candles: null,
  rsiMarkers: null,
  smaSeries: {},
  smaVisibility: { sma20: false, sma50: false, sma200: false },
};

function chartMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " $";
}

function chartPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function chartNum(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
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
    cell.innerHTML = '<button type="button" class="chart-btn" title="Open chart" aria-label="Open chart">📊</button>';
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
  chartStatus("Loading chart...");
  fetchTradeData(positionId, null);
}

async function fetchTradeData(positionId, preserveRange = null) {
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
    drawTradeChart(trade, preserveRange);

    chartStatus("Chart updated: " + new Date().toLocaleString("en-US"));
  } catch (error) {
    // During a refresh, keep the existing chart (and its zoom) visible if the
    // new dataset cannot be loaded. On first open there is no chart to preserve.
    if (!tradeChartState.chart) destroyTradeChart();
    chartStatus("Chart loading error: " + error.message, true);
  }
}

function renderTradeHeader(trade) {
  chartEl("tradeChartTitle").textContent = trade.ticker + " — " + (trade.strategy_type || "SWING");
  chartEl("tradeChartSubtitle").textContent =
    "Entry " + chartMoney(trade.entry_price) + " · " +
    (trade.status === "CLOSED" ? "Closed Trade" : "Open Position");
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

  let divergenceLabel = "No significant RSI divergence";
  let divergenceClass = "neutral";
  if (bullish.length && bearish.length) {
    divergenceLabel = "Bullish + Bearish divergence";
    divergenceClass = "mixed";
  } else if (bullish.length) {
    divergenceLabel = "Bullish divergence present";
    divergenceClass = "bullish";
  } else if (bearish.length) {
    divergenceLabel = "Bearish divergence present";
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
      VIX is shown as market context only. It is not plotted and does not affect scoring. Divergences are diagnostic analysis based on price + RSI14, not automatic signals. The dashed line is a possible path toward the target, not a forecast.
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
  tradeChartState.smaSeries = {};
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

              if (zone.label && right - left > 90 && height >= 10) {
                ctx.font = "600 11px Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
                ctx.fillStyle = style.text;
                ctx.textAlign = "right";
                ctx.textBaseline = "middle";
                const labelY = top + Math.min(Math.max(height / 2, 10), height - 5);
                ctx.fillText(zone.label, right - 8, labelY);
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
      text: bullish ? "B1" : "D1",
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
      lineStyle: window.LightweightCharts.LineStyle.Solid,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      title: bullish ? "Bullish divergence" : "Bearish divergence",
      priceScaleId: "rsi",
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

function ensureSmaControls() {
  const actions = document.querySelector(".chart-dialog-actions");
  if (!actions) return;

  if (actions.querySelector("[data-sma-toggle]")) {
    updateSmaButtons();
    return;
  }

  [
    ["sma20", "SMA20"],
    ["sma50", "SMA50"],
    ["sma200", "SMA200"],
  ].forEach(([key, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chart-action indicator-toggle";
    button.dataset.smaToggle = key;
    button.textContent = label;
    button.title = "Show / hide " + label;
    button.addEventListener("click", () => toggleSma(key));
    actions.insertBefore(button, actions.firstChild);
  });

  updateSmaButtons();
}

function updateSmaButtons() {
  document.querySelectorAll("[data-sma-toggle]").forEach((button) => {
    const key = button.dataset.smaToggle;
    const active = Boolean(tradeChartState.smaVisibility[key]);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function toggleSma(key) {
  tradeChartState.smaVisibility[key] = !tradeChartState.smaVisibility[key];
  const series = tradeChartState.smaSeries[key];
  if (series) {
    series.applyOptions({ visible: tradeChartState.smaVisibility[key] });
  }
  updateSmaButtons();
}


function addTargetProjection(chart, trade, bars, LineSeries, LineStyle) {
  if (!trade || trade.status === "CLOSED" || !Array.isArray(bars) || bars.length < 2) return;

  const target = Number(trade.target);
  const current = Number(bars[bars.length - 1]?.close);
  if (!Number.isFinite(target) || !Number.isFinite(current)) return;

  const distance = target - current;
  if (Math.abs(distance) < Math.max(Math.abs(current) * 0.002, 0.01)) return;

  // Estimate a modest horizon from the planned swing horizon and the number of
  // sessions already elapsed. The path is deliberately a scenario, not a signal.
  const entryTime = Number(trade.entry_time);
  const elapsedSessions = Number.isFinite(entryTime)
    ? bars.filter((bar) => Number(bar.time) > entryTime).length
    : 0;
  const plannedHorizon = Number(trade.planned_horizon_sessions) || 20;
  const remainingSessions = Math.max(4, Math.min(20, plannedHorizon - elapsedSessions || 8));
  const projectionPoints = Math.max(4, remainingSessions);

  // Use the recent slope only as a small curvature bias, while forcing the
  // projection to start at the latest realtime close and end exactly at target.
  const recent = bars.slice(-12).map((bar) => Number(bar.close)).filter(Number.isFinite);
  let slope = 0;
  if (recent.length >= 3) {
    const n = recent.length;
    const xMean = (n - 1) / 2;
    const yMean = recent.reduce((sum, value) => sum + value, 0) / n;
    let numerator = 0;
    let denominator = 0;
    for (let i = 0; i < n; i += 1) {
      numerator += (i - xMean) * (recent[i] - yMean);
      denominator += (i - xMean) ** 2;
    }
    if (denominator > 0) slope = numerator / denominator;
  }

  const maxBias = Math.abs(distance) * 0.20;
  const bias = Math.max(-maxBias, Math.min(maxBias, slope * projectionPoints * 0.25));
  const points = [];
  const startTime = Number(bars[bars.length - 1].time);
  let cursor = new Date(startTime * 1000);

  points.push({ time: startTime, value: current });

  for (let step = 1; step <= projectionPoints; step += 1) {
    cursor = new Date(cursor.getTime());
    do {
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    } while (cursor.getUTCDay() === 0 || cursor.getUTCDay() === 6);

    const t = step / projectionPoints;
    const eased = t * t * (3 - 2 * t); // smooth-step: starts gently, ends cleanly.
    const curve = bias * Math.sin(Math.PI * t);
    const value = current + (distance * eased) + curve;

    points.push({
      time: Math.floor(cursor.getTime() / 1000),
      value,
    });
  }

  const projection = chart.addSeries(LineSeries, {
    color: "rgba(255, 255, 255, 0.78)",
    lineWidth: 2,
    lineStyle: LineStyle.Dashed,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
    title: "Possible target projection",
  });
  projection.setData(points);
}

function drawTradeChart(trade, preserveRange = null) {
  destroyTradeChart();

  if (!window.LightweightCharts) {
    chartStatus("Chart library unavailable.", true);
    return;
  }
  if (!trade.bars || trade.bars.length === 0) {
    chartStatus("Historical data unavailable.", true);
    return;
  }

  const {
    createChart,
    CandlestickSeries,
    LineSeries,
    LineStyle,
  } = window.LightweightCharts;

  const container = chartEl("tradeChartCanvas");
  ensureSmaControls();

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

  tradeChartState.smaSeries = {};
  const maConfig = [
    ["sma20", "SMA20", "rgba(240,195,106,0.68)", 1.5],
    ["sma50", "SMA50", "rgba(110,168,254,0.60)", 1.5],
    ["sma200", "SMA200", "rgba(169,120,214,0.52)", 1.5],
  ];
  maConfig.forEach(([key, title, color, width]) => {
    const line = chart.addSeries(LineSeries, {
      color,
      lineWidth: width,
      priceLineVisible: false,
      lastValueVisible: false,
      title,
      visible: Boolean(tradeChartState.smaVisibility[key]),
    });
    line.setData(barSeriesData(trade.bars, key));
    tradeChartState.smaSeries[key] = line;
  });

  // Trade-plan levels are intentionally dominant. The colored bands below make
  // the reward/risk structure immediately readable without hiding the candles.
  addPriceLine(candles, trade.entry_price, "ENTRY", "#76b7ff", LineStyle.Solid, 2);
  addPriceLine(candles, trade.stop, "STOP LOSS", "#ff4f6d", LineStyle.Solid, 2);
  addPriceLine(candles, trade.target, "TARGET", "#2fe39a", LineStyle.Solid, 2);

  if (trade.exit_price !== null && trade.exit_price !== undefined) {
    addPriceLine(candles, trade.exit_price, "EXIT", "#ffd166", LineStyle.Solid, 2);
  }

  attachZonePrimitive(chart, candles, trade.zones || [], trade.bars, trade);

  addTargetProjection(chart, trade, trade.bars, LineSeries, LineStyle);

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
  if (preserveRange && typeof preserveRange === "object") {
    try {
      chart.timeScale().setVisibleRange(preserveRange);
    } catch (error) {
      // If the refreshed dataset changed enough to invalidate the old time range,
      // keep the freshly fitted view instead of resetting or breaking the chart.
    }
  }
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

  let visibleRange = null;
  if (tradeChartState.chart) {
    try {
      visibleRange = tradeChartState.chart.timeScale().getVisibleRange();
    } catch (error) {
      visibleRange = null;
    }
  }

  chartStatus("Updating chart...");
  fetchTradeData(tradeChartState.positionId, visibleRange);
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
