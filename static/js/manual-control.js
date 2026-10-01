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
      {label: t('requested_chart'), data: [], borderColor: '#f59e0b', yAxisID: 'duty', stepped: true},
      {label: t('gpio_chart'), data: [], borderColor: '#34d399', yAxisID: 'gpio', stepped: true},
      {label: t('measured_chart'), data: [], borderColor: '#a78bfa', yAxisID: 'voltage', spanGaps: false}
    ]}, options: {responsive: true, maintainAspectRatio: false, animation: false,
      interaction: {mode: 'index', intersect: false}, elements: {point: {radius: 0}},
      scales: {temperature: {position: 'left', title: {display: true, text: '°C'}},
        duty: {position: 'right', min: 0, max: 100, title: {display: true, text: t('voltage_axis')}, grid: {drawOnChartArea: false}},
        gpio: {display: false, min: 0, max: 1}, voltage: {display: false, min: 0, max: 3.6}}}
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
    const fresh = Boolean(state?.live && Date.now() - Date.parse(state.temperature_at) <= 10000);
    const overheated = fresh && state.overheat;
    const gap = state ? state.target_temperature - state.temperature : null;
    const approaching = Boolean(fresh && state.active && !overheated &&
      state.temperature !== null && gap > 0 && gap <= 1 && Number(target.value) === state.target_temperature);
    const reached = Boolean(state?.active && state.live && !state.overheat &&
      state.status === 'at_target' && state.temperature >= state.target_temperature &&
      Number(target.value) === state.target_temperature &&
      Date.now() - Date.parse(state.temperature_at) <= 10000);
    document.getElementById('manual-target-card').classList.toggle('is-target-reached', reached);
    document.getElementById('manual-target-card').classList.toggle('is-target-approaching', approaching);
    document.getElementById('manual-target-card').classList.toggle('is-overheated', Boolean(overheated));
    document.getElementById('manual-target-reached').classList.toggle('d-none', !reached);
    document.getElementById('manual-target-approaching').classList.toggle('d-none', !approaching);
    document.getElementById('manual-target-overheated').classList.toggle('d-none', !overheated);
  }
  function render(state) {
    latestState = state;
    highlightTarget(state);
    setText('live-temperature', state.temperature === null ? '— °C' : `${number(state.temperature)} °C`);
    const trend = state.delta > 0 ? 'rising' : state.delta < 0 ? 'falling' : 'steady';
    document.getElementById('temperature-trend').className = `temperature-trend trend-${trend}`;
    document.getElementById('temperature-trend-icon').className = `bi bi-arrow-${trend === 'rising' ? 'up-right' : trend === 'falling' ? 'down-right' : 'right'}`;
    setText('temperature-change', state.delta === null ? '—' : `${state.delta > 0 ? '+' : ''}${number(state.delta)} °C`);
    setText('temperature-previous', state.previous_temperature === null ? t('no_previous') : t('previous_reading', {temperature: number(state.previous_temperature)}));
    const eta = state.eta_status === 'estimated' ? (state.eta_seconds < 60 ?
      t('eta_seconds', {seconds: state.eta_seconds}) : t('eta_minutes', {minutes: Math.ceil(state.eta_seconds / 60)})) :
      state.eta_status === 'collecting' ? t('eta_collecting', {intervals: state.estimate_intervals}) : t(`eta_${state.eta_status}`);
    setText('heating-eta', eta);
    setText('heating-rate', state.heating_rate_c_per_min === null ? t('eta_hint') : t('heating_rate', {rate: number(state.heating_rate_c_per_min)}));
    setText('vessel-description', t('vessel_description', {name: state.vessel_name, volume: number(state.volume_liters, 1)}));
    setText('temperature-time', state.temperature_at ? `${t(state.live ? 'live' : 'stale_data')} · ${time(state.temperature_at)}` : t('waiting_sensor'));
    setText('ssr-voltage', t(state.ssr_on === null ? 'gpio_unknown' : state.ssr_on ? 'gpio_on' : 'gpio_off'));
    setText('ssr-power', state.power_percent === null ? '—' : t('time_duty', {power: number(state.power_percent, 1)}));
    setText('ssr-timing', state.on_time_ms === null ? '—' : t('time_window', {
      window: number(state.reported_window_ms / 1000), on: number(state.on_time_ms / 1000),
      off: number((state.reported_window_ms - state.on_time_ms) / 1000)
    }));
    setText('manual-status', t(state.status));
    document.getElementById('manual-status').className = `badge rounded-pill text-bg-${state.overheat ? 'danger' : state.active ? 'success' : 'secondary'}`;
    setText('saved-target', t('saved_target', {target: number(state.target_temperature), threshold: number(state.warning_temperature)}));
    const warning = document.getElementById('manual-warning');
    warning.classList.toggle('d-none', !state.overheat && !state.reported_fault && state.status !== 'no_data');
    setText('manual-warning', state.overheat ? t('overheat_warning', {temperature: number(state.temperature), target: number(state.target_temperature)}) : state.reported_fault ? t('pid_fault') : t('no_data_warning'));
    const reportFresh = state.reported_at && Date.now() - Date.parse(state.reported_at) <= 10000;
    const confirmed = state.output_confirmed;
    setText('esp-report', confirmed ? t('esp_applied', {time: time(state.reported_at)}) : t('esp_waiting'));
    setText('ssr-measured', state.measured_voltage == null ? t('adc_missing') : `${t('adc_measured', {voltage: number(state.measured_voltage, 3)})}${reportFresh ? '' : ` · ${t('stale_measurement')}`}`);
    form.querySelector('[value="start"]').disabled = busy || state.active;
    stop.disabled = !state.active;
    if (state.history && chart && chartSince !== null) {
      const history = state.history.filter(point => Date.parse(point.at) >= Date.parse(chartSince));
      chart.data.labels = history.map(point => time(point.at));
      chart.data.datasets[0].data = history.map(point => point.temperature);
      chart.data.datasets[1].data = history.map(point => point.target);
      chart.data.datasets[2].data = history.map(point => point.power_percent);
      chart.data.datasets[3].data = history.map(point => point.ssr_on === null ? null : Number(point.ssr_on));
      chart.data.datasets[4].data = history.map(point => point.measured_voltage);
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
