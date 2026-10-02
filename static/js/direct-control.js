(() => {
  const panel = document.getElementById('direct-panel');
  const messages = JSON.parse(document.getElementById('direct-messages').textContent);
  const t = (key, values = {}) => messages[key].replace(/%\((\w+)\)s/g, (_, name) => values[name]);
  const number = value => new Intl.NumberFormat(document.documentElement.lang, {maximumFractionDigits: 3}).format(value);
  const error = document.getElementById('direct-error');
  const stop = document.getElementById('direct-stop');
  const inputs = ['heater', 'pump'].map(name => document.getElementById(`direct-${name}`));
  let busy = false, polling = false, state = null;
  const text = (id, value) => { document.getElementById(id).textContent = value; };
  function render(value) {
    state = value;
    const conflict = !state.direct_mode && state.active;
    const fresh = state.reported_at && Date.now() - Date.parse(state.reported_at) <= 10000;
    ['heater', 'pump'].forEach((name, index) => {
      const requested = state.direct_mode && (name === 'heater' ? state.active : state.pump_on);
      const actual = fresh ? (name === 'heater' ? state.ssr_on : state.reported_pump_on) : null;
      inputs[index].checked = Boolean(requested);
      inputs[index].disabled = busy || conflict || (!requested && !state.live);
      text(`${name}-state-text`, t(actual == null ? 'unknown' : actual ? 'on' : 'off'));
      document.getElementById(`${name}-state`).className = `output-status mt-3 output-status-${actual == null ? 'unknown' : actual ? 'on' : 'off'}`;
      document.getElementById(`${name}-state-icon`).className = `bi ${actual == null ? 'bi-question-circle' : actual ? 'bi-check-circle-fill' : 'bi-power'}`;
      if (name === 'heater') text('heater-voltage', actual == null ? '— V' : `${number(actual ? 3.3 : 0)} V`);
    });
    const requestedOn = state.direct_mode && (state.active || state.pump_on);
    const reportedOn = fresh && (state.ssr_on === true || state.reported_pump_on === true);
    stop.disabled = busy || conflict || !(requestedOn || reportedOn);
    const measured = fresh && state.pump_voltage != null && state.pump_current != null;
    text('pump-voltage', fresh && state.pump_voltage != null ? `${number(state.pump_voltage)} V` : '— V');
    text('pump-current', fresh && state.pump_current != null ? `${number(state.pump_current)} A` : '— A');
    text('pump-monitor-status', t(measured ? 'monitor_live' : 'monitor_missing'));
    text('heater-measured', fresh && state.measured_voltage != null ? t('adc', {voltage: number(state.measured_voltage)}) : t('adc_missing'));
    text('direct-confirmation', conflict ? t('pid') : state.output_confirmed ? t('confirmed') : t('waiting'));
  }
  function fail(message) { error.textContent = message; error.classList.remove('d-none'); }
  async function refresh() {
    if (busy || polling) return;
    polling = true;
    try {
      const response = await fetch(panel.dataset.statusUrl, {cache: 'no-store', signal: AbortSignal.timeout(8000)});
      if (!response.ok) throw new Error(t('status_error'));
      const data = await response.json();
      if (!busy) render(data);
    } catch (e) { if (state && !busy) render({...state, reported_at: null, output_confirmed: false, live: false}); fail(e instanceof TypeError || ['TimeoutError', 'AbortError'].includes(e.name) ? t('network') : e.message); } finally { polling = false; }
  }
  async function command(output, on) {
    if (busy || (output === 'all' && stop.disabled)) return;
    busy = true;
    inputs.forEach(input => { input.disabled = true; });
    stop.disabled = true;
    error.classList.add('d-none');
    try {
      const body = new FormData(document.getElementById('direct-token'));
      body.set('output', output); body.set('on', String(on));
      const response = await fetch(panel.dataset.actionUrl, {method: 'POST', body, signal: AbortSignal.timeout(8000)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || t('rejected'));
      state = data;
    } catch (e) { fail(e instanceof TypeError || ['TimeoutError', 'AbortError'].includes(e.name) ? t('network') : e.message); }
    finally { busy = false; if (state) render(state); refresh(); }
  }
  inputs.forEach((input, index) => input.addEventListener('change', () => command(index ? 'pump' : 'heater', input.checked)));
  stop.addEventListener('click', () => command('all', false));
  refresh(); setInterval(refresh, 3000);
})();
