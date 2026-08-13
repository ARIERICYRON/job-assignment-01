const states = new Map();
const grid = document.querySelector('#grid');
const empty = document.querySelector('#empty');
const status = document.querySelector('#connection-status');
const errorBox = document.querySelector('#error');
const SNAPSHOT_TIMEOUT_MS = 5000;
const RETRY_DELAY_MS = 1000;
let stopped = false;
let retryTimer;
let snapshotRetryTimer;
let socket;
let snapshotPromise;
let refreshRequested = false;
let updatesDuringSnapshot;
let realtimeConnected = false;

function stateKey(state) {
  return JSON.stringify([state.deviceId, state.metric]);
}

function isNewer(candidate, current) {
  return (
    candidate.generation > current.generation ||
    (candidate.generation === current.generation &&
      candidate.sequence > current.sequence)
  );
}

function applyUpdate(state, target = states) {
  const key = stateKey(state);
  const current = target.get(key);
  if (!current || isNewer(state, current)) {
    target.set(key, state);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function render() {
  const ordered = [...states.values()].sort(
    (left, right) =>
      left.deviceId.localeCompare(right.deviceId) ||
      left.metric.localeCompare(right.metric)
  );

  empty.classList.toggle('hidden', ordered.length > 0);
  grid.innerHTML = ordered
    .map(
      (state) => `
        <article>
          <div class="card-title">
            <h2>${escapeHtml(state.deviceId)}</h2>
            <span>${escapeHtml(state.metric)}</span>
          </div>
          <strong>${Number(state.value).toFixed(2)}</strong>
          <dl>
            <div><dt>Generation</dt><dd>${state.generation}</dd></div>
            <div><dt>Sequence</dt><dd>${state.sequence}</dd></div>
            <div><dt>Boot</dt><dd title="${escapeHtml(state.bootId)}">${escapeHtml(state.bootId.slice(0, 8))}</dd></div>
            <div><dt>Received</dt><dd>${new Date(state.receivedAt).toLocaleTimeString()}</dd></div>
          </dl>
        </article>
      `
    )
    .join('');
}

function setError(message) {
  errorBox.textContent = message || '';
  errorBox.classList.toggle('hidden', !message);
}

async function fetchSnapshot() {
  const controller = new AbortController();
  const timeoutTimer = window.setTimeout(
    () => controller.abort(),
    SNAPSHOT_TIMEOUT_MS
  );
  try {
    const response = await fetch('/api/devices', { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`Snapshot request failed with ${response.status}.`);
    }

    const body = await response.json();
    return body.devices;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Snapshot request timed out.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutTimer);
  }
}

function clearSnapshotRetry() {
  window.clearTimeout(snapshotRetryTimer);
  snapshotRetryTimer = undefined;
}

function scheduleSnapshotRetry() {
  if (snapshotRetryTimer || stopped || !realtimeConnected) {
    return;
  }
  snapshotRetryTimer = window.setTimeout(() => {
    snapshotRetryTimer = undefined;
    if (!stopped && realtimeConnected) {
      void loadSnapshot();
    }
  }, RETRY_DELAY_MS);
}

async function applySnapshot() {
  const bufferedUpdates = new Map();
  updatesDuringSnapshot = bufferedUpdates;
  try {
    const devices = await fetchSnapshot();
    states.clear();
    for (const state of devices) {
      states.set(stateKey(state), state);
    }
    for (const state of bufferedUpdates.values()) {
      applyUpdate(state);
    }
    render();
    clearSnapshotRetry();
    setError('');
  } finally {
    if (updatesDuringSnapshot === bufferedUpdates) {
      updatesDuringSnapshot = undefined;
    }
  }
}

async function loadSnapshot() {
  refreshRequested = true;
  if (snapshotPromise) {
    return snapshotPromise;
  }

  snapshotPromise = (async () => {
    while (refreshRequested) {
      refreshRequested = false;
      try {
        await applySnapshot();
      } catch (error) {
        setError(error.message);
        if (!refreshRequested) {
          scheduleSnapshotRetry();
        }
      }
    }
  })();

  try {
    await snapshotPromise;
  } finally {
    snapshotPromise = undefined;
    if (refreshRequested) {
      void loadSnapshot();
    }
  }
}

function connect() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

  socket.addEventListener('open', () => {
    realtimeConnected = true;
    clearSnapshotRetry();
    status.textContent = 'Realtime connected';
    status.className = 'status online';
    setError('');
    void loadSnapshot();
  });

  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.type !== 'device.state.changed') {
      return;
    }
    if (updatesDuringSnapshot) {
      applyUpdate(message.data, updatesDuringSnapshot);
    }
    applyUpdate(message.data);
    render();
  });

  socket.addEventListener('error', () => {
    setError('Realtime connection failed.');
  });

  socket.addEventListener('close', () => {
    realtimeConnected = false;
    clearSnapshotRetry();
    status.textContent = 'Realtime disconnected';
    status.className = 'status offline';
    if (!stopped) {
      retryTimer = window.setTimeout(connect, RETRY_DELAY_MS);
    }
  });
}

loadSnapshot().catch((error) => setError(error.message));
connect();

window.addEventListener('beforeunload', () => {
  stopped = true;
  window.clearTimeout(retryTimer);
  clearSnapshotRetry();
  socket?.close();
});
