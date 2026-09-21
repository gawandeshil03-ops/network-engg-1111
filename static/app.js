const refreshButton = document.getElementById('refreshButton');
const lastRefresh = document.getElementById('lastRefresh');
const onlineCount = document.getElementById('onlineCount');
const averageLatency = document.getElementById('averageLatency');
const historyTarget = document.getElementById('historyTarget');
const historyMessage = document.getElementById('historyMessage');
const latencyChart = document.getElementById('latencyChart');
const packetLossChart = document.getElementById('packetLossChart');

const SVG_NS = 'http://www.w3.org/2000/svg';
let refreshInProgress = false;

function text(value, suffix = '') {
  return value === null || value === undefined ? '—' : `${value}${suffix}`;
}

function setCard(result) {
  const card = document.querySelector(`[data-target-id="${result.id}"]`);
  if (!card) return;

  card.classList.remove('loading', 'online', 'offline');
  card.classList.add(result.online ? 'online' : 'offline');

  const badge = card.querySelector('.status-badge');
  badge.textContent = result.online ? 'Online' : 'Offline';

  card.querySelector('[data-field="latency"]').textContent = text(result.latency_ms, ' ms');
  card.querySelector('[data-field="loss"]').textContent = text(result.packet_loss, '%');
  card.querySelector('[data-field="dns"]').textContent = result.dns_ip || 'Failed';
  card.querySelector('[data-field="port"]').textContent =
    result.port === null ? 'Not configured' : (result.port_open ? `${result.port} open` : `${result.port} closed`);
  card.querySelector('[data-field="uptime"]').textContent = text(result.uptime_percent, '%');
  card.querySelector('[data-field="error"]').textContent = result.error || '';
}

function svgElement(name, attributes = {}, value = null) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, attributeValue]) => {
    element.setAttribute(key, attributeValue);
  });
  if (value !== null) element.textContent = value;
  return element;
}

function formatChartTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function updateChartStats(prefix, values, suffix) {
  const latest = document.getElementById(`${prefix}Latest`);
  const average = document.getElementById(`${prefix}Average`);
  const peak = document.getElementById(`${prefix}Peak`);

  if (!values.length) {
    latest.textContent = '—';
    average.textContent = '—';
    peak.textContent = '—';
    return;
  }

  const latestValue = values[values.length - 1];
  const averageValue = values.reduce((sum, value) => sum + value, 0) / values.length;
  const peakValue = Math.max(...values);

  latest.textContent = `${latestValue.toFixed(1)}${suffix}`;
  average.textContent = `${averageValue.toFixed(1)}${suffix}`;
  peak.textContent = `${peakValue.toFixed(1)}${suffix}`;
}

function renderTimeSeries(svg, history, key, unit, fixedMaximum = null) {
  svg.replaceChildren();

  const width = 720;
  const height = 280;
  const margin = { top: 18, right: 18, bottom: 40, left: 54 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = history.map(row => typeof row[key] === 'number' ? row[key] : null);
  const numericValues = values.filter(value => value !== null);

  if (!numericValues.length) {
    svg.appendChild(svgElement('text', {
      x: width / 2,
      y: height / 2,
      class: 'empty-label'
    }, `No ${key === 'latency_ms' ? 'latency' : 'packet loss'} data yet`));
    return;
  }

  const observedMaximum = Math.max(...numericValues);
  const dynamicMaximum = observedMaximum <= 0
    ? 10
    : Math.ceil((observedMaximum * 1.2) / 5) * 5;
  const yMaximum = fixedMaximum ?? Math.max(10, dynamicMaximum);
  const xForIndex = index => history.length === 1
    ? margin.left + plotWidth / 2
    : margin.left + (index / (history.length - 1)) * plotWidth;
  const yForValue = value => margin.top + plotHeight - (Math.min(value, yMaximum) / yMaximum) * plotHeight;

  for (let step = 0; step <= 4; step += 1) {
    const ratio = step / 4;
    const y = margin.top + ratio * plotHeight;
    const labelValue = yMaximum * (1 - ratio);

    svg.appendChild(svgElement('line', {
      x1: margin.left,
      y1: y,
      x2: width - margin.right,
      y2: y,
      class: 'grid-line'
    }));
    svg.appendChild(svgElement('text', {
      x: margin.left - 10,
      y: y + 3,
      class: 'axis-label',
      'text-anchor': 'end'
    }, `${labelValue.toFixed(labelValue >= 10 ? 0 : 1)}${unit}`));
  }

  const labelIndexes = [...new Set([0, Math.floor((history.length - 1) / 2), history.length - 1])];
  labelIndexes.forEach((index, position) => {
    const anchor = position === 0 ? 'start' : (position === labelIndexes.length - 1 ? 'end' : 'middle');
    svg.appendChild(svgElement('text', {
      x: xForIndex(index),
      y: height - 10,
      class: 'axis-label',
      'text-anchor': anchor
    }, formatChartTime(history[index].checked_at)));
  });

  let segment = [];
  const segments = [];
  values.forEach((value, index) => {
    if (value === null) {
      if (segment.length) segments.push(segment);
      segment = [];
      return;
    }
    segment.push({ index, value });
  });
  if (segment.length) segments.push(segment);

  segments.forEach(points => {
    const path = points.map((point, pointIndex) => {
      const command = pointIndex === 0 ? 'M' : 'L';
      return `${command} ${xForIndex(point.index)} ${yForValue(point.value)}`;
    }).join(' ');

    if (points.length > 1) {
      const first = points[0];
      const last = points[points.length - 1];
      const areaPath = `${path} L ${xForIndex(last.index)} ${margin.top + plotHeight} L ${xForIndex(first.index)} ${margin.top + plotHeight} Z`;
      svg.appendChild(svgElement('path', { d: areaPath, class: 'area-fill' }));
    }
    svg.appendChild(svgElement('path', { d: path, class: 'series-line' }));
  });

  if (history.length <= 40) {
    values.forEach((value, index) => {
      if (value === null) return;
      const dot = svgElement('circle', {
        cx: xForIndex(index),
        cy: yForValue(value),
        r: 3,
        class: 'series-dot'
      });
      dot.appendChild(svgElement('title', {}, `${formatChartTime(history[index].checked_at)} · ${value.toFixed(1)}${unit}`));
      svg.appendChild(dot);
    });
  }
}

async function loadHistory() {
  if (!historyTarget || historyTarget.disabled || !historyTarget.value) return;

  historyMessage.textContent = 'Loading measurement history…';
  try {
    const response = await fetch(`/api/history/${historyTarget.value}?limit=60`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const history = data.history || [];

    renderTimeSeries(latencyChart, history, 'latency_ms', ' ms');
    renderTimeSeries(packetLossChart, history, 'packet_loss', '%', 100);

    const latencyValues = history
      .map(row => row.latency_ms)
      .filter(value => typeof value === 'number');
    const lossValues = history
      .map(row => row.packet_loss)
      .filter(value => typeof value === 'number');

    updateChartStats('latency', latencyValues, ' ms');
    updateChartStats('loss', lossValues, '%');

    const selectedName = historyTarget.options[historyTarget.selectedIndex]?.text || 'target';
    historyMessage.textContent = history.length
      ? `${history.length} stored checks shown for ${selectedName}.`
      : 'No stored measurements yet. Run a check to create the first data point.';
  } catch (error) {
    historyMessage.textContent = 'Could not load chart history.';
    console.error(error);
  }
}

async function refreshStatus() {
  if (refreshInProgress) return;
  refreshInProgress = true;
  refreshButton.disabled = true;
  refreshButton.textContent = 'Checking…';

  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    data.targets.forEach(setCard);
    const online = data.targets.filter(item => item.online).length;
    const latencies = data.targets.map(item => item.latency_ms).filter(value => typeof value === 'number');

    onlineCount.textContent = `${online}/${data.targets.length}`;
    averageLatency.textContent = latencies.length
      ? `${(latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(1)} ms`
      : '—';
    lastRefresh.textContent = new Date().toLocaleTimeString();
    await loadHistory();
  } catch (error) {
    lastRefresh.textContent = 'Refresh failed';
    console.error(error);
  } finally {
    refreshInProgress = false;
    refreshButton.disabled = false;
    refreshButton.textContent = 'Run checks now';
  }
}

refreshButton.addEventListener('click', refreshStatus);
if (historyTarget) historyTarget.addEventListener('change', loadHistory);
refreshStatus();
setInterval(refreshStatus, 30000);
