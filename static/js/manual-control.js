(() => {
  const panel = document.getElementById('manual-panel');
  const form = document.getElementById('manual-form');
  const target = document.getElementById('manual-target');
  const slider = document.getElementById('target-range');
  const stop = document.getElementById('manual-stop');
  const chartRefresh = document.getElementById('manual-chart-refresh');
  const errorBox = document.getElementById('manual-error');
  const messages = JSON.parse(document.getElementById('manual-messages').textContent);
  const t = (key, values = {}) => messages[key].replace(/%\((\w+)\)s|%%/g,
    (match, name) => name ? String(values[name]) : '%');
  const locale = document.documentElement.lang;
  const number = (value, digits = 2) => new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0, maximumFractionDigits: digits
  }).format(value);
  const time = value => new Date(value).toLocaleTimeString(locale);
  const setText = (id, text) => {
    const element = document.getElementById(id);
    if (element.textContent !== text) element.textContent = text;
  };
  const errorMessage = error => ['TimeoutError', 'AbortError', 'TypeError'].includes(error.name) ? t('network_error') : error.message;
  let busy = false;
  let polling = false;
  let stopRequested = false;
  let chartSince = null;
  let chartVersion = 0;
  let latestState = null;
  const chart = typeof Chart === 'undefined' ? null : new Chart(document.getElementById('manual-chart'), {
    type: 'line', data: {labels: [], datasets: [
      {label: t('sensor_chart'), data: [], borderColor: '#38bdf8', yAxisID: 'temperature', tension: .25},
      {label: t('target_chart'), data: [], borderColor: '#94a3b8', borderDash: [6, 4], yAxisID: 'temperature'},
      {label: t('requested_chart'), data: [], borderColor: '#f59e0b', yAxisID: 'voltage', stepped: true},
      {label: t('measured_chart'), data: [], borderColor: '#a78bfa', yAxisID: 'voltage', spanGaps: false}
    ]}, options: {responsive: true, maintainAspectRatio: false, animation: false,
      interaction: {mode: 'index', intersect: false}, elements: {point: {radius: 0}},
      scales: {temperature: {position: 'left', title: {display: true, text: '°C'}},
        voltage: {position: 'right', min: 0, max: 3.6, title: {display: true, text: t('voltage_axis')}, grid: {drawOnChartArea: false}}}}
  });
  function resetChart(since) {
    chartVersion += 1;
    chartSince = since;
    chartRefresh.disabled = since === null;
    if (!chart) return;
    chart.data.labels = [];
    chart.data.datasets.forEach(dataset => { dataset.data = []; });
    chart.update();
  }
  function highlightTarget(state) {
    const reached = Boolean(state?.active && state.live && !state.overheat &&
      state.status === 'at_target' && state.temperature >= state.target_temperature &&
      Number(target.value) === state.target_temperature &&
      Date.now() - Date.parse(state.temperature_at) <= 10000);
    document.getElementById('manual-target-card').classList.toggle('is-target-reached', reached);
    document.getElementById('manual-target-reached').classList.toggle('d-none', !reached);
  }
  function render(state) {
    latestState = state;
    highlightTarget(state);
    setText('live-temperature', state.temperature === null ? '— °C' : `${number(state.temperature)} °C`);
    const trend = state.delta === null ? t('no_previous') : t('trend', {
      change: `${state.delta > 0 ? '↑ +' : state.delta < 0 ? '↓ ' : '→ '}${number(state.delta)}`,
      previous: number(state.previous_temperature)
    });
    setText('temperature-trend', trend);
    setText('temperature-time', state.temperature_at ? `${t(state.live ? 'live' : 'stale_data')} · ${time(state.temperature_at)}` : t('waiting_sensor'));
    setText('ssr-voltage', t('voltage', {voltage: number(state.signal_voltage)}));
    setText('ssr-power', t('power', {power: number(state.power_percent, 1)}));
    setText('manual-status', t(state.status));
    document.getElementById('manual-status').className = `badge rounded-pill text-bg-${state.overheat ? 'danger' : state.active ? 'success' : 'secondary'}`;
    setText('saved-target', t('saved_target', {target: number(state.target_temperature), threshold: number(state.warning_temperature)}));
    const warning = document.getElementById('manual-warning');
    warning.classList.toggle('d-none', !state.overheat && state.status !== 'no_data');
    setText('manual-warning', state.overheat ? t('overheat_warning', {temperature: number(state.temperature), target: number(state.target_temperature)}) : t('no_data_warning'));
    const reportFresh = state.reported_at && Date.now() - Date.parse(state.reported_at) <= 10000;
    const confirmed = reportFresh && state.reported_output_mode === 'pwm' && state.reported_revision === state.revision && Math.abs(state.reported_power - state.power_percent) < .1;
    setText('esp-report', confirmed ? t('esp_applied', {power: number(state.reported_power, 1), time: time(state.reported_at)}) : t('esp_waiting'));
    setText('ssr-measured', state.measured_voltage == null ? t('adc_missing') : `${t('adc_measured', {voltage: number(state.measured_voltage, 3)})}${reportFresh ? '' : ` · ${t('stale_measurement')}`}`);
    form.querySelector('[value="start"]').disabled = busy || state.active;
    stop.disabled = !state.active;
    if (state.history && chart && chartSince !== null) {
      const history = state.history.filter(point => Date.parse(point.at) >= Date.parse(chartSince));
      chart.data.labels = history.map(point => time(point.at));
      chart.data.datasets[0].data = history.map(point => point.temperature);
      chart.data.datasets[1].data = history.map(point => point.target);
      chart.data.datasets[2].data = history.map(point => point.voltage);
      chart.data.datasets[3].data = history.map(point => point.measured_voltage);
      chart.update();
    }
  }
  function showError(message) { errorBox.textContent = message; errorBox.classList.remove('d-none'); }
  async function refresh() {
    if (polling || busy) return;
    polling = true;
    try {
      const response = await fetch(panel.dataset.statusUrl, {cache: 'no-store', signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error(t('status_error'));
      const state = await response.json();
      if (!busy) render(state);
    } catch (error) { highlightTarget(null); showError(errorMessage(error)); }
    finally { polling = false; }
  }
  async function action(name) {
    if (busy) { if (name === 'stop') stopRequested = true; return; }
    busy = true;
    chartRefresh.disabled = true;
    errorBox.classList.add('d-none');
    const body = name === 'stop' ? new FormData() : new FormData(form);
    body.set('action', name);
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
    try {
      const response = await fetch(panel.dataset.actionUrl, {method: 'POST', body,
        headers: {'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value}, signal: AbortSignal.timeout(8000)});
      const state = await response.json();
      if (!response.ok) throw new Error(state.detail || Object.values(state.errors || {}).flat().join(' ') || t('action_error'));
      if (state.chart_since) resetChart(state.chart_since);
      render(state);
    } catch (error) { showError(`${errorMessage(error)} ${t('retry_hint')}`); }
    finally {
      busy = false;
      form.querySelector('[value="apply"]').disabled = false;
      form.querySelector('[value="start"]').disabled = latestState?.active === true;
      chartRefresh.disabled = chartSince === null;
      if (stopRequested) { stopRequested = false; action('stop'); } else refresh();
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); action(event.submitter.value); });
  stop.addEventListener('click', () => action('stop'));
  chartRefresh.addEventListener('click', async () => {
    const version = chartVersion;
    chartRefresh.disabled = true;
    try {
      const url = new URL(panel.dataset.statusUrl, window.location.href);
      url.searchParams.set('reset_chart', '1');
      const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error(t('status_error'));
      const state = await response.json();
      if (chartVersion !== version) return;
      resetChart(state.chart_since);
      if (!busy) render(state);
    } catch (error) { showError(errorMessage(error)); }
    finally { chartRefresh.disabled = busy || chartSince === null; }
  });
  slider.addEventListener('input', () => { target.value = slider.value; highlightTarget(latestState); });
  target.addEventListener('input', () => { slider.value = target.value; highlightTarget(latestState); });
  for (const [id, delta] of [['target-minus', -1], ['target-plus', 1]]) {
    document.getElementById(id).addEventListener('click', () => { target.value = Math.min(100, Math.max(30, Math.round(Number(target.value)) + delta)); slider.value = target.value; highlightTarget(latestState); });
  }
  refresh();
  window.setInterval(refresh, 3000);
})();
