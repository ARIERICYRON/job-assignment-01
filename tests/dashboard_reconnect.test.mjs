import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..'
);
const appSource = readFileSync(
  path.join(projectRoot, 'telemetry_gateway', 'static', 'app.js'),
  'utf8'
);

class FakeElement {
  constructor() {
    this.className = '';
    this.innerHTML = '';
    this.textContent = '';
    this.classList = { toggle() {} };
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function snapshot(devices, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return { devices };
    },
  };
}

function deviceState(sequence, value = 20 + sequence, overrides = {}) {
  return {
    deviceId: 'device-01',
    bootId: 'boot-a',
    generation: 1,
    sequence,
    deviceTime: `2026-08-12T09:00:${String(sequence).padStart(2, '0')}Z`,
    receivedAt: `2026-08-12T09:01:${String(sequence).padStart(2, '0')}Z`,
    metric: 'temperature',
    value,
    ...overrides,
  };
}

function createHarness(fetchResponses) {
  const fetchCalls = [];
  const sockets = [];
  const timers = [];
  let nextTimerId = 1;
  const elements = new Map([
    ['#grid', new FakeElement()],
    ['#empty', new FakeElement()],
    ['#connection-status', new FakeElement()],
    ['#error', new FakeElement()],
  ]);

  class FakeWebSocket {
    constructor(url) {
      this.url = url;
      this.listeners = new Map();
      sockets.push(this);
    }

    addEventListener(type, listener) {
      const listeners = this.listeners.get(type) ?? [];
      listeners.push(listener);
      this.listeners.set(type, listeners);
    }

    emit(type, payload = {}) {
      for (const listener of this.listeners.get(type) ?? []) {
        listener(payload);
      }
    }

    close() {}
  }

  const window = {
    location: { host: '127.0.0.1:3000', protocol: 'http:' },
    addEventListener() {},
    clearTimeout(id) {
      const timer = timers.find((candidate) => candidate.id === id);
      if (timer) {
        timer.cancelled = true;
      }
    },
    setTimeout(callback, delay) {
      const timer = {
        callback,
        cancelled: false,
        delay,
        id: nextTimerId,
      };
      nextTimerId += 1;
      timers.push(timer);
      return timer.id;
    },
  };
  const context = vm.createContext({
    WebSocket: FakeWebSocket,
    console,
    document: {
      querySelector(selector) {
        return elements.get(selector);
      },
    },
    AbortController,
    DOMException,
    async fetch(url, options = {}) {
      fetchCalls.push(url);
      assert.ok(fetchResponses.length > 0, 'unexpected snapshot request');
      const response = fetchResponses.shift();
      if (!options.signal) {
        return await response;
      }
      return await Promise.race([
        response,
        new Promise((_, reject) => {
          options.signal.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true }
          );
        }),
      ]);
    },
    window,
  });

  vm.runInContext(appSource, context, { filename: 'app.js' });

  return {
    currentState() {
      return vm.runInContext(
        "states.get(JSON.stringify(['device-01', 'temperature']))",
        context
      );
    },
    currentStates() {
      return vm.runInContext('[...states.values()]', context);
    },
    fetchCalls,
    runTimer(delay) {
      const timer = timers.find(
        (candidate) => !candidate.cancelled && candidate.delay === delay
      );
      assert.ok(timer, `no active ${delay}ms timer`);
      timer.cancelled = true;
      timer.callback();
    },
    sockets,
    timers,
  };
}

async function settle() {
  for (let index = 0; index < 4; index += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

test('loads a snapshot after the initial connection and every reconnect', async () => {
  const harness = createHarness([
    Promise.resolve(snapshot([])),
    Promise.resolve(snapshot([deviceState(1)])),
    Promise.resolve(snapshot([deviceState(2)])),
  ]);
  await settle();

  assert.equal(harness.fetchCalls.length, 1);
  harness.sockets[0].emit('open');
  await settle();
  assert.equal(harness.fetchCalls.length, 2);

  harness.sockets[0].emit('close');
  harness.runTimer(1000);
  harness.sockets[1].emit('open');
  await settle();

  assert.equal(harness.fetchCalls.length, 3);
  assert.equal(harness.currentState().sequence, 2);
});

test('retries when a reconnect snapshot fails without another refresh pending', async () => {
  const failedSnapshot = deferred();
  const harness = createHarness([
    Promise.resolve(snapshot([])),
    failedSnapshot.promise,
    Promise.resolve(snapshot([deviceState(2)])),
  ]);
  await settle();

  harness.sockets[0].emit('open');
  failedSnapshot.reject(new Error('reconnect snapshot failed'));
  await settle();
  assert.equal(harness.fetchCalls.length, 2);

  harness.runTimer(1000);
  await settle();

  assert.equal(harness.fetchCalls.length, 3);
  assert.equal(harness.currentState().sequence, 2);
});

test('times out a hung snapshot and retries while connected', async () => {
  const hungSnapshot = deferred();
  const harness = createHarness([
    Promise.resolve(snapshot([])),
    hungSnapshot.promise,
    Promise.resolve(snapshot([deviceState(2)])),
  ]);
  await settle();

  harness.sockets[0].emit('open');
  await settle();
  assert.equal(harness.fetchCalls.length, 2);

  harness.runTimer(5000);
  await settle();
  harness.runTimer(1000);
  await settle();

  assert.equal(harness.fetchCalls.length, 3);
  assert.equal(harness.currentState().sequence, 2);
});

test('retries an open-triggered refresh after an overlapping snapshot fails', async () => {
  const firstSnapshot = deferred();
  const harness = createHarness([
    firstSnapshot.promise,
    Promise.resolve(snapshot([deviceState(2)])),
  ]);

  assert.equal(harness.fetchCalls.length, 1);
  harness.sockets[0].emit('open');
  firstSnapshot.reject(new Error('startup snapshot failed'));
  await settle();

  assert.equal(harness.fetchCalls.length, 2);
  assert.equal(harness.currentState().sequence, 2);
});

test('keeps device and metric identifier pairs collision-free', async () => {
  const harness = createHarness([
    Promise.resolve(
      snapshot([
        deviceState(1, 21, { deviceId: 'a:b', metric: 'c' }),
        deviceState(1, 22, { deviceId: 'a', metric: 'b:c' }),
      ])
    ),
  ]);
  await settle();

  assert.equal(harness.currentStates().length, 2);
});

test('keeps a live update received while a snapshot is in flight', async () => {
  const reconnectSnapshot = deferred();
  const harness = createHarness([
    Promise.resolve(snapshot([])),
    reconnectSnapshot.promise,
  ]);
  await settle();

  harness.sockets[0].emit('open');
  await settle();
  assert.equal(harness.fetchCalls.length, 2);

  harness.sockets[0].emit('message', {
    data: JSON.stringify({
      type: 'device.state.changed',
      data: deviceState(2),
    }),
  });
  assert.equal(harness.currentState().sequence, 2);

  reconnectSnapshot.resolve(snapshot([deviceState(1)]));
  await settle();

  assert.equal(harness.currentState().sequence, 2);
});
