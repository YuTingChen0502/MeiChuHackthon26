import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { balanceText, buildProbePlan, canMutate, commandFor, confidenceText, deviceDiscoveryText, displayStatus, expandInstrumentConfiguration, fixtureLiveSnapshot, fixtureRehearsal, fixtureScenario, freshness, liveViewState, receiptIsFresh, restoreProbeView, runtimeErrorText, runtimeInstrumentGroups, runtimeReadiness, sessionCondition, SETUP_ENDPOINT_PLAN } from '../../apps/ui/app.js';
import { RuntimeAdapter } from '../../apps/ui/runtime-adapter.js';

const confidence = (abstained = false) => ({ abstained, reasons: abstained ? ['noise_overlap'] : [], calibration_status: abstained ? 'out_of_envelope' : 'calibrated', probability: abstained ? null : .9, magnitude_tolerance_db: 1.5 });
const active = (status, balance, c = confidence()) => ({ activity:'active', status, balance_deviation_db:balance, confidence:c });

test('shows numeric balance only for valid active non-abstained states', () => {
  assert.equal(balanceText(active('too_loud', 4.1)), '+4.1 dB');
  assert.equal(balanceText(active('normal', 0)), '+0.0 dB');
  assert.equal(balanceText(active('unknown', null, confidence(true))), 'Balance unavailable');
});
test('renders explicit inactive and abstained states', () => {
  assert.equal(displayStatus({ activity:'inactive', status:'inactive', confidence:confidence(true) }), 'Inactive · Abstained');
  assert.equal(displayStatus({ activity:'inactive', status:'inactive', confidence:confidence(false) }), 'Inactive');
  assert.equal(displayStatus(active('too_quiet', -2.4)), 'Too Quiet');
  assert.equal(displayStatus({ activity:'unknown', status:'unknown', confidence:confidence(true) }), 'Unknown / Not Observable · Abstained');
});
test('marks stale and static fixture data without pretending it is fresh', () => {
  assert.equal(freshness({ example_only:true, published_monotonic_s:5, quality:{ stale:true } }, 8), 'Stale fixture frame — do not act');
  assert.equal(freshness({ example_only:true, published_monotonic_s:5, quality:{ stale:false } }), 'Fixture/static frame — data age unavailable');
  assert.equal(freshness({ example_only:false, published_monotonic_s:5, quality:{ stale:false } }, 8), '3.0 s old');
});
test('fixture mode never permits mutations and expired local receipt freshness is gated', () => {
  const snapshot = { session_id:'s-1' };
  assert.equal(canMutate('fixture', { snapshot }, snapshot, true), false);
  assert.equal(receiptIsFresh({ quality:{ stale:false } }, 1_000, true, 7_000), false);
  assert.equal(receiptIsFresh({ quality:{ stale:false } }, 2_000, true, 6_000), true);
  assert.equal(receiptIsFresh({ quality:{ stale:true } }, 2_000, true, 2_100), false);
});
test('renders tolerance as probability semantics and only renders an actual interval', () => {
  const withoutInterval = confidence(false);
  withoutInterval.probability_event = 'joint_anomaly_numeric_correct';
  withoutInterval.prediction_interval_db = null;
  assert.match(confidenceText(withoutInterval), /Magnitude tolerance: ±1.5 dB/);
  assert.doesNotMatch(confidenceText(withoutInterval), /Prediction interval/);
  withoutInterval.prediction_interval_db = [-1, 2];
  assert.match(confidenceText(withoutInterval), /Prediction interval: -1 to 2 dB/);
});
test('command binds exactly to currently displayed snapshot identities', () => {
  const snapshot = { session_id:'s-1', state_version:7, active_reference:{reference_id:'r-1',source_asset_hash:'hash'}, active_baseline:{baseline_id:'b-1',version:3}, incident:{event:{event_id:'e-1'},event_version:2} };
  const command = commandFor(snapshot, 'pause', {}, 'key-1');
  assert.deepEqual(command.reference, {reference_id:'r-1',source_asset_hash:'hash'});
  assert.deepEqual(command.baseline, {baseline_id:'b-1',baseline_version:3});
  assert.deepEqual(command.event, {event_id:'e-1',event_version:2});
  assert.equal(command.expected_state_version, 7);
});
test('setup follows the frozen L2 API order', () => {
  assert.deepEqual(SETUP_ENDPOINT_PLAN.map(line => line.split('  ')[0]), ['POST /v1/projects','POST /v1/songs','POST /v1/audio-assets','POST /v1/songs/{id}/reference','GET /v1/jobs/{id}','POST /v1/sessions']);
});
test('quantity setup creates duplicate performer identities but one honest Runtime family group', () => {
  const instances = expandInstrumentConfiguration([['guitar',2],['vocal',1],['keyboard',0]]);
  assert.deepEqual(instances.map(x => x.instrument_id), ['guitar-1','guitar-2','vocal-1']);
  assert.deepEqual(runtimeInstrumentGroups(instances), [
    { instrument_id:'guitar', family:'guitar' },
    { instrument_id:'vocal', family:'vocal' },
  ]);
});
test('guided rehearsal is dynamic and ends with quiet, loud, then explicit review', () => {
  const plan = buildProbePlan(expandInstrumentConfiguration([['guitar',2],['drums',1]]));
  assert.deepEqual(plan.map(x => x.kind), ['instrument','instrument','instrument','full_band_quiet','full_band_loud','review']);
  assert.equal(plan[0].label, 'Please play Guitar 1');
  assert.equal(plan.at(-1).label, 'Calibration review');
});
test('reconnect restores only the probe detail Runtime actually persisted', () => {
  const plan = buildProbePlan(expandInstrumentConfiguration([['guitar',2],['drums',1]]));
  const instrument = restoreProbeView(plan, { mode:'instrument', instrument_id:'guitar', probe_id:'probe-1' });
  assert.equal(instrument.index, 0);
  assert.equal(instrument.step.label, 'Resume Guitar family probe');
  assert.doesNotMatch(instrument.step.label, /Guitar [12]/);
  const fullBand = restoreProbeView(plan, { mode:'full_band', instrument_id:null, probe_id:'probe-2' });
  assert.equal(fullBand.step.label, 'Resume the active full-band probe');
  assert.doesNotMatch(fullBand.step.label, /quiet|loud/i);
  assert.equal(restoreProbeView(plan, { mode:'idle' }), null);
});
test('authoritative anomaly outranks unrelated abstention in the Live presentation', () => {
  const snapshot = {
    song:{ workflow_state:'LIVE_ANOMALY' }, incident_state:'active', latest_verification:null,
    latest_frame:{ instruments:[active('too_loud', 3.5), active('unknown', null, confidence(true))] },
  };
  assert.equal(liveViewState(snapshot), 'anomaly');
});
test('renders Runtime, model, and native discovery truth without promoting simulation', () => {
  assert.equal(runtimeReadiness({ provider:'fake-simulated', model_bundle_id:'fake-v1', example_only:true }), 'Simulation / fixture analyzer · fake-simulated · fake-v1');
  assert.equal(runtimeReadiness({ provider:'CPUExecutionProvider', model_bundle_id:'adapted-v1', example_only:false }), 'Runtime analyzer · CPUExecutionProvider · adapted-v1');
  assert.equal(deviceDiscoveryText({ discovery_status:'available', devices:[{device_id:'device-1'}] }), '1 native microphone input available');
  assert.equal(deviceDiscoveryText({ discovery_status:'native_backend_unavailable', devices:[] }), 'Native microphone backend unavailable');
  assert.match(deviceDiscoveryText({ discovery_status:'injected_example_only', devices:[{device_id:'mic-fixture'}] }), /not physical capture evidence/);
  assert.match(runtimeErrorText({ payload:{ error:{ code:'model_unavailable' } } }), /HTTP 503/);
});
test('renders suspended, degraded, waiting, simulated, and authoritative session conditions from Runtime fields', () => {
  assert.deepEqual(sessionCondition({ song:{workflow_state:'SUSPENDED'}, suspension_reasons:['audio_device_lost'] }), { label:'Suspended', detail:'audio_device_lost' });
  assert.equal(sessionCondition({ song:{workflow_state:'REHEARSAL'}, latest_frame:null }).label, 'Waiting for evidence');
  assert.equal(sessionCondition({ song:{workflow_state:'REHEARSAL'}, latest_frame:{example_only:true,quality:{stale:false,dropout:false,capture_compatible:true,comparability:'comparable'}} }).label, 'Simulation evidence only');
  assert.equal(sessionCondition({ song:{workflow_state:'REHEARSAL'}, latest_frame:{example_only:false,quality:{stale:true,dropout:false,capture_compatible:true,comparability:'comparable',reason_codes:['stale_analysis']}} }).label, 'Unavailable / degraded evidence');
  assert.equal(sessionCondition({ song:{workflow_state:'REHEARSAL'}, latest_frame:{example_only:false,quality:{stale:false,dropout:false,capture_compatible:true,comparability:'comparable'}} }).label, 'Authoritative Runtime evidence');
});
test('derived fixture frames only contain declared families and correct profile bindings', async () => {
  const fixtures = JSON.parse(await readFile(new URL('../../contracts/examples/pa_shared_v1.json', import.meta.url)));
  const live = fixtureScenario(fixtures);
  for (const snapshot of [live, fixtureRehearsal(fixtures)]) {
    const declared = new Set(snapshot.song.configured_families);
    assert.deepEqual(new Set(snapshot.latest_frame.instruments.map(item => item.instrument_id)), declared);
    assert.equal(snapshot.latest_frame.session_id, snapshot.session_id);
    assert.equal(snapshot.latest_frame.reference_id, snapshot.active_reference.reference_id);
    assert.equal(snapshot.latest_frame.baseline_id, snapshot.active_baseline?.baseline_id ?? null);
  }
  const guitar = live.latest_frame.instruments.find(item => item.instrument_id === 'guitar');
  const bass = live.latest_frame.instruments.find(item => item.instrument_id === 'bass');
  assert.deepEqual(guitar.confidence.prediction_interval_db, [2.6, 5.6]);
  assert.equal(bass.confidence.probability_event, 'normal_within_envelope');
  assert.equal(live.recommendations[0].suggested_step_db, -2);
});
test('runtime adapter posts commands to the frozen route and refreshes a conflict snapshot', async () => {
  const originalFetch = globalThis.fetch;
  const received = [];
  const refreshed = [];
  globalThis.fetch = async (url, options) => {
    received.push([url, options]);
    return { ok:false, status:409, json:async () => ({ error:{ message:'stale' }, snapshot:{ session_id:'s-1', state_version:8 } }) };
  };
  try {
    const adapter = new RuntimeAdapter({ onSnapshot:snapshot => refreshed.push(snapshot), onStatus() {} });
    adapter.activateSession('s-1');
    await assert.rejects(() => adapter.command({ session_id:'s-1', action:'pause' }), /stale/);
    assert.equal(received[0][0], '/v1/sessions/s-1/actions');
    assert.equal(received[0][1].method, 'POST');
    assert.deepEqual(refreshed, [{ session_id:'s-1', state_version:8 }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
test('runtime adapter ignores delayed snapshots and refreshes after a frame-only event', async () => {
  const originalFetch = globalThis.fetch;
  const snapshots = [];
  globalThis.fetch = async () => ({ ok:true, status:200, json:async () => ({ session_id:'s-1', state_version:3, event_sequence:3 }) });
  try {
    const adapter = new RuntimeAdapter({ onSnapshot:snapshot => snapshots.push(snapshot), onStatus() {} });
    adapter.activateSession('s-1');
    adapter.acceptSnapshot({ session_id:'s-1', state_version:3, event_sequence:2 });
    assert.equal(adapter.acceptSnapshot({ session_id:'s-1', state_version:2, event_sequence:1 }), false);
    await adapter.handleEvent('s-1', { session_id:'s-1', event_sequence:3, payload:{ record_type:'AnalysisFrame' } });
    assert.deepEqual(snapshots, [{ session_id:'s-1', state_version:3, event_sequence:2 }, { session_id:'s-1', state_version:3, event_sequence:3 }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
test('runtime adapter reconnects from a fresh snapshot cursor', async () => {
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const originalLocation = globalThis.location;
  const sockets = [];
  const urls = [];
  globalThis.fetch = async url => {
    urls.push(url);
    const payload = url.endsWith('/probes')
      ? { record_type:'RehearsalProbeState', schema_version:'1.0', session_id:'s-1', state_version:4, mode:'idle', instrument_id:null, probe_id:null, not_before_monotonic_s:null }
      : { session_id:'s-1', state_version:4, event_sequence:9 };
    return { ok:true, status:200, json:async () => payload };
  };
  globalThis.location = { protocol:'http:', host:'127.0.0.1:8000' };
  globalThis.WebSocket = class { constructor(url) { this.url = url; sockets.push(this); } close() {} };
  try {
    const adapter = new RuntimeAdapter({ onSnapshot() {}, onStatus() {} });
    adapter.activateSession('s-1');
    await adapter.recover('s-1');
    assert.match(sockets[0].url, /after_sequence=9$/);
    assert.deepEqual(urls, ['/v1/sessions/s-1', '/v1/sessions/s-1/probes']);
    adapter.stopEvents();
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
    globalThis.location = originalLocation;
  }
});
test('runtime adapter isolates cursor and late responses across deliberate session switches', async () => {
  const snapshots = [];
  const adapter = new RuntimeAdapter({ onSnapshot:snapshot => snapshots.push(snapshot), onStatus() {} });
  adapter.activateSession('old');
  adapter.acceptSnapshot({ session_id:'old', state_version:4, event_sequence:50 });
  adapter.activateSession('new');
  adapter.acceptSnapshot({ session_id:'new', state_version:0, event_sequence:0 });
  await adapter.handleEvent('new', { session_id:'new', event_sequence:1, payload:{ record_type:'SessionSnapshot', session_id:'new', state_version:1, event_sequence:1 } });
  assert.equal(adapter.cursor, 1);
  assert.equal(adapter.acceptSnapshot({ session_id:'old', state_version:5, event_sequence:51 }), false);
  assert.equal(adapter.snapshot.session_id, 'new');
  assert.deepEqual(snapshots.map(snapshot => snapshot.session_id), ['old', 'new', 'new']);
});
test('runtime adapter binds guided probe requests exactly and restores probe state on GET', async () => {
  const originalFetch = globalThis.fetch;
  const received = [];
  const nextSnapshot = { session_id:'s-1', state_version:8, event_sequence:8 };
  const probe = { record_type:'RehearsalProbeState', schema_version:'1.0', session_id:'s-1', state_version:8, mode:'instrument', instrument_id:'guitar', probe_id:'probe-1', not_before_monotonic_s:12.5 };
  globalThis.fetch = async (url, options={}) => {
    received.push([url, options]);
    const payload = options.method === 'POST'
      ? { record_type:'RehearsalProbeResponse', schema_version:'1.0', command:{ snapshot:nextSnapshot }, probe }
      : probe;
    return { ok:true, status:200, json:async () => payload };
  };
  try {
    const snapshots = [];
    const adapter = new RuntimeAdapter({ onSnapshot:value => snapshots.push(value), onStatus() {} });
    adapter.activateSession('s-1');
    const displayed = {
      session_id:'s-1', state_version:7,
      active_reference:{ reference_id:'reference-1', source_asset_hash:'hash-1' },
      active_baseline:{ baseline_id:'baseline-1', version:2 },
      incident:{ event:{ event_id:'event-1' }, event_version:3 },
    };
    await adapter.requestProbe(displayed, 'instrument', 'guitar');
    const body = JSON.parse(received[0][1].body);
    assert.equal(received[0][0], '/v1/sessions/s-1/probes');
    assert.equal(body.record_type, 'RehearsalProbeCommand');
    assert.equal(body.expected_state_version, 7);
    assert.deepEqual(body.reference, { reference_id:'reference-1', source_asset_hash:'hash-1' });
    assert.deepEqual(body.baseline, { baseline_id:'baseline-1', baseline_version:2 });
    assert.deepEqual(body.event, { event_id:'event-1', event_version:3 });
    assert.equal(body.mode, 'instrument');
    assert.equal(body.instrument_id, 'guitar');
    assert.deepEqual(snapshots, [nextSnapshot]);
    assert.deepEqual(await adapter.probeState(), probe);
    assert.equal(received[1][0], '/v1/sessions/s-1/probes');
    assert.equal(adapter.probe, probe);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
test('fixture Live renders normal, anomaly, abstain, and recovered only as example evidence', async () => {
  const base = JSON.parse(await readFile(new URL('../../contracts/examples/pa_shared_v1.json', import.meta.url)));
  for (const state of ['normal','anomaly','abstain','recovered']) {
    const current = fixtureLiveSnapshot(base, state);
    assert.equal(current.latest_frame.example_only, true);
    assert.equal(liveViewState(current), state);
  }
  const abstain = fixtureLiveSnapshot(base, 'abstain');
  assert.ok(abstain.latest_frame.instruments.every(x => x.balance_deviation_db === null && x.confidence.abstained));
  const rehearsal = fixtureRehearsal(base);
  rehearsal.song.name = 'Configured locally';
  rehearsal.active_baseline = structuredClone(base.live_snapshot.active_baseline);
  const transitioned = fixtureLiveSnapshot(base, 'normal', rehearsal);
  assert.equal(transitioned.song.name, 'Configured locally');
  assert.equal(transitioned.active_baseline.baseline_id, rehearsal.active_baseline.baseline_id);
});
test('runtime adapter loads a selected authoritative session and gates controls until its socket connects', async () => {
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const originalLocation = globalThis.location;
  const connections = [];
  globalThis.fetch = async url => {
    const payload = url.endsWith('/probes')
      ? { record_type:'RehearsalProbeState', schema_version:'1.0', session_id:'session-2', state_version:2, mode:'idle', instrument_id:null, probe_id:null, not_before_monotonic_s:null }
      : { session_id:'session-2', state_version:2, event_sequence:7 };
    return { ok:true, status:200, json:async () => payload };
  };
  globalThis.location = { protocol:'http:', host:'127.0.0.1:8000' };
  globalThis.WebSocket = class { constructor(url) { this.url=url; } close() {} };
  try {
    const adapter = new RuntimeAdapter({ onSnapshot() {}, onStatus() {}, onConnection:value => connections.push(value) });
    const snapshot = await adapter.openSession('session-2');
    assert.equal(snapshot.session_id, 'session-2');
    assert.equal(adapter.activeSessionId, 'session-2');
    assert.equal(adapter.probe.mode, 'idle');
    assert.match(adapter.socket.url, /after_sequence=7$/);
    assert.deepEqual(connections, [false]);
    adapter.stopEvents();
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
    globalThis.location = originalLocation;
  }
});
test('setup requests native capture without claiming browser-verified physical properties', async () => {
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const originalLocation = globalThis.location;
  const requests = [];
  const responses = [
    { project_id:'project-1' },
    { song_id:'song-1' },
    { asset_id:'asset-1' },
    { job_id:'job-1', status:'queued' },
    { job_id:'job-1', status:'completed', reference_id:'reference-1' },
    { session_id:'session-1', state_version:0, event_sequence:0 },
  ];
  globalThis.fetch = async (url, options={}) => {
    requests.push([url, options]);
    return { ok:true, status:200, json:async () => responses.shift() };
  };
  globalThis.location = { protocol:'http:', host:'127.0.0.1:8000' };
  globalThis.WebSocket = class { constructor(url) { this.url=url; } close() {} };
  try {
    const adapter = new RuntimeAdapter({ onSnapshot() {}, onStatus() {} });
    await adapter.setup({ project:'Demo', song:'Song', families:['guitar'], reference:{name:'reference.wav'}, source:'live_microphone', sourceId:'native-1' });
    const sessionBody = JSON.parse(requests.at(-1)[1].body);
    assert.deepEqual(sessionBody.source, { input_kind:'live_microphone', input_asset_or_device_id:'native-1' });
    assert.equal(sessionBody.capture_fingerprint.gain_setting, null);
    assert.equal(sessionBody.capture_fingerprint.enhancements_verified_disabled, null);
    assert.equal(sessionBody.capture_fingerprint.geometry_id, null);
    assert.equal(sessionBody.capture_fingerprint.provenance, 'unverified');
    assert.equal(sessionBody.capture_fingerprint.profile_id, 'ui-request-v1');
    assert.equal(sessionBody.capture_fingerprint.native_sample_rate_hz, 48000);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
    globalThis.location = originalLocation;
  }
});
test('isolated demo player has no Runtime transport or filename rendering path', async () => {
  const player = await readFile(new URL('../../demo_player/player.js', import.meta.url), 'utf8');
  assert.doesNotMatch(player, /\bfetch\s*\(|\bXMLHttpRequest\b|\bWebSocket\b/);
  assert.doesNotMatch(player, /\.name\b/);
  assert.match(player, /prepared clip \$\{selectedIndex \+ 1\} of \$\{selectedUrls\.length\}/);
});
test('UI source contains no client-side audio inference or automatic mixer execution', async () => {
  const source = await readFile(new URL('../../apps/ui/app.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /AudioContext|AnalyserNode|getUserMedia|automatic_execution\s*:\s*true/);
  assert.match(source, /Runtime remains the only evidence source/);
});
test('responsive card grid supports variable counts without fixed four-card selectors', async () => {
  const css = await readFile(new URL('../../apps/ui/styles.css', import.meta.url), 'utf8');
  assert.match(css, /repeat\(auto-fit,minmax/);
  assert.doesNotMatch(css, /nth-child\(4\)/);
});
