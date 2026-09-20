import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { balanceText, buildProbePlan, calibrationDraftFor, canMutate, commandFor, commandGuard, confidenceText, currentRecoveredVerification, deviceDiscoveryText, displayStatus, expandInstrumentConfiguration, fixtureLiveSnapshot, fixtureRehearsal, fixtureScenario, freshness, liveEvidenceState, liveViewState, microphoneOptions, modelSupportSummary, normalizeCatalogRows, receiptIsFresh, referenceProgressText, restoreConfiguredInstances, restoreProbeView, runtimeErrorText, runtimeInstrumentGroups, runtimeReadiness, sessionCondition, sourceIdentityText, sourcePresentation, SETUP_ENDPOINT_PLAN, verificationPresentation } from '../../apps/ui/app.js';
import { pollReferenceJob, RuntimeAdapter } from '../../apps/ui/runtime-adapter.js';

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
  assert.equal(displayStatus({ activity:'unknown', status:'unknown', confidence:confidence(true) }), 'Insufficient Evidence');
  assert.equal(displayStatus({ activity:'unsupported', status:'unsupported', confidence:confidence(true) }), 'Unsupported / Insufficient Evidence');
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
  assert.equal(receiptIsFresh({ quality:{ stale:false } }, 2_000, true, 2_999, 12_000, 3_000), true);
  assert.equal(receiptIsFresh({ quality:{ stale:false } }, 2_000, true, 3_000, 12_000, 3_000), false);
  assert.equal(receiptIsFresh({ quality:{ stale:false } }, 2_000, true, 3_000, 12_000, null), false);
});
test('real command guards reject disconnected or stale actionable state but retain safe stop', () => {
  const snapshot = { session_id:'s-1', latest_frame:{ quality:{ stale:false } } };
  const adapter = { snapshot:{ session_id:'s-1' } };
  assert.equal(commandGuard('start_adjustment','authoritative',adapter,snapshot,false,1_000,1_100).allowed, false);
  assert.equal(commandGuard('recheck','authoritative',adapter,snapshot,true,1_000,7_000).allowed, false);
  assert.equal(commandGuard('accept_baseline','authoritative',adapter,snapshot,true,1_000,2_000).allowed, true);
  assert.equal(commandGuard('stop','authoritative',adapter,snapshot,false,null,99_000).allowed, true);
  assert.equal(commandGuard('pause','fixture',adapter,snapshot,true,1_000,1_100).allowed, false);
  snapshot.analysis_timing={receipt_max_age_s:12};
  assert.equal(commandGuard('start_adjustment','authoritative',adapter,snapshot,true,1_000,1_999,2_000).allowed, true);
  assert.equal(commandGuard('start_adjustment','authoritative',adapter,snapshot,true,1_000,2_000,2_000).allowed, false);
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
test('uncalibrated confidence never renders probability or numeric precision', () => {
  const value = confidenceText({calibration_status:'uncalibrated',calibration_id:null,probability:.99,probability_event:'joint_anomaly_numeric_correct',magnitude_tolerance_db:1.5,prediction_interval_db:[-1,1],abstained:true,reasons:['uncalibrated_uncertainty']});
  assert.equal(value, 'Uncalibrated · Abstained · uncalibrated_uncertainty');
  assert.doesNotMatch(value, /%|tolerance|interval/i);
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
test('Live never reports normal or recovered without fresh observable and relevant evidence', () => {
  const base = { song:{ workflow_state:'LIVE_MONITORING' }, incident_state:'none', latest_verification:null, active_baseline:{baseline_id:'b-1',version:1} };
  assert.equal(liveViewState(base), 'waiting');
  const stale = { ...base, latest_frame:{ quality:{stale:true}, instruments:[active('normal',0)] } };
  assert.equal(liveViewState(stale), 'unavailable');
  const unsupported = { ...base, latest_frame:{ quality:{stale:false,dropout:false,capture_compatible:true,comparability:'comparable'}, instruments:[{...active('unsupported',null,confidence(true)),activity:'unsupported'}] } };
  assert.equal(liveEvidenceState(unsupported), 'unsupported');
  assert.equal(liveViewState(unsupported), 'abstain');
  const oldRecovered = { ...base, incident_state:'active', song:{workflow_state:'LIVE_ANOMALY'}, incident:{event:{event_id:'new'}}, latest_frame:{ quality:{stale:false}, instruments:[active('too_loud',3)] }, latest_verification:{outcome:'recovered',event_id:'old',baseline_id:'b-1',baseline_version:1} };
  assert.equal(liveViewState(oldRecovered), 'anomaly');
  assert.equal(currentRecoveredVerification(oldRecovered), false);
  const normal = { ...base, latest_frame:{ quality:{stale:false,dropout:false,capture_compatible:true,comparability:'comparable'}, instruments:[active('normal',0)] } };
  assert.equal(liveViewState(normal,1_000,true,7_000), 'unavailable');
  const pending = { ...normal, latest_frame:{...normal.latest_frame,instruments:[active('too_loud',2.5)]} };
  assert.equal(liveViewState(pending), 'monitoring');
  const resolvedButUnknown = { ...normal, incident_state:'resolved', incident:{event:{event_id:'e-1'}}, latest_frame:{...normal.latest_frame,instruments:[{...active('unknown',null,confidence(true)),activity:'unknown'}]}, latest_verification:{outcome:'recovered',event_id:'e-1',baseline_id:'b-1',baseline_version:1} };
  assert.equal(currentRecoveredVerification(resolvedButUnknown), true);
  assert.equal(liveViewState(resolvedButUnknown), 'abstain');
});
test('verification presentation exposes waiting, partial and inconclusive Runtime outcomes', () => {
  assert.deepEqual(verificationPresentation({adjustment:{adjustment_id:'a-2',completed_monotonic_s:4},latest_verification:{adjustment_id:'a-1'}}).state, 'waiting');
  const partial = verificationPresentation({adjustment:null,latest_verification:{outcome:'partial',source_observable:true,before_balance_db:4,after_balance_db:2,reason_codes:[]}});
  assert.equal(partial.title, 'Partially improved');
  assert.match(partial.detail, /Before 4.0 dB · after 2.0 dB/);
  const inconclusive = verificationPresentation({adjustment:null,latest_verification:{outcome:'inconclusive',source_observable:false,before_balance_db:4,after_balance_db:null,reason_codes:['source_not_observable']}});
  assert.equal(inconclusive.title, 'Verification inconclusive');
  assert.match(inconclusive.detail, /source_not_observable/);
});
test('renders Runtime, model, and native discovery truth without promoting simulation', () => {
  assert.equal(runtimeReadiness({ provider:'fake-simulated', model_bundle_id:'fake-v1', example_only:true }), 'Fake / simulated analyzer · fake-simulated · fake-v1');
  assert.equal(runtimeReadiness({ provider:'CPUExecutionProvider', model_bundle_id:'nano4-p1-adapted-mvp-v1', example_only:false }), 'Real / candidate analyzer · CPUExecutionProvider · nano4-p1-adapted-mvp-v1');
  assert.equal(deviceDiscoveryText({ discovery_status:'available', devices:[{device_id:'device-1'}] }), '1 native microphone input available');
  assert.equal(deviceDiscoveryText({ discovery_status:'native_backend_unavailable', devices:[] }), 'Native microphone backend unavailable');
  assert.match(deviceDiscoveryText({ discovery_status:'injected_example_only', devices:[{device_id:'mic-fixture'}] }), /not physical capture evidence/);
  assert.match(runtimeErrorText({ payload:{ error:{ code:'model_unavailable' } } }), /HTTP 503/);
});
test('uses friendly microphone labels without exposing stable native IDs', () => {
  const devices=[
    {device_id:'portaudio:opaque-default',name:'USB Audio',host_api:'WASAPI',is_default:true},
    {device_id:'portaudio:opaque-second',name:'USB Audio',host_api:'MME',is_default:false},
    {device_id:'legacy-injected-id'},
    {device_id:'portaudio:unique',name:'Stage Interface',host_api:'WASAPI'},
  ];
  assert.deepEqual(microphoneOptions(devices),[
    {device_id:'portaudio:opaque-default',label:'USB Audio (Default) · WASAPI'},
    {device_id:'portaudio:opaque-second',label:'USB Audio · MME'},
    {device_id:'legacy-injected-id',label:'Microphone input 3'},
    {device_id:'portaudio:unique',label:'Stage Interface'},
  ]);
  const discovery={devices};
  assert.equal(sourceIdentityText({input_kind:'live_microphone',input_asset_or_device_id:'portaudio:opaque-default'},discovery),'live microphone · USB Audio (Default) · WASAPI');
  assert.equal(sourceIdentityText({input_kind:'live_microphone',input_asset_or_device_id:'missing-opaque-id'},discovery),'live microphone · Microphone input');
  assert.doesNotMatch(sourceIdentityText({input_kind:'live_microphone',input_asset_or_device_id:'portaudio:opaque-second'},discovery),/opaque|portaudio/);
  assert.equal(sourceIdentityText({input_kind:'uploaded_file',input_asset_or_device_id:'asset-7'},discovery),'uploaded file · asset-7');
});
test('labels song configuration without inventing model coverage', () => {
  const snapshot={song:{configured_families:['bass','guitar','drums','vocals','keys'],unsupported_families:['guitar','drums','vocals','keys']}};
  assert.equal(modelSupportSummary(snapshot),'Configured instrument families · bass, guitar, drums, vocals, keys');
  assert.equal(liveEvidenceState({...snapshot,latest_frame:{quality:{stale:false,dropout:false,capture_compatible:true,comparability:'comparable'},instruments:[active('normal',0)]}}),'unsupported');
});

test('empty song unsupported list never implies candidate support in diagnostics', () => {
  const snapshot={song:{configured_families:['bass','guitar','drums','vocals','keys'],unsupported_families:[]},perception:[{family:'bass',state:'uncertain'},...['guitar','drums','vocals','keys'].map(family=>({family,state:'unsupported'}))]};
  const original=structuredClone(snapshot);
  assert.equal(modelSupportSummary(snapshot),'Configured instrument families · bass, guitar, drums, vocals, keys');
  assert.doesNotMatch(modelSupportSummary(snapshot),/supported|coverage/i);
  assert.equal(modelSupportSummary({song:{configured_families:[]}}),'Instrument configuration unavailable');
  assert.equal(modelSupportSummary(null),'Instrument configuration unavailable');
  assert.deepEqual(snapshot,original);
});
test('source status distinguishes file, microphone, connection, suspension, stale and errors', () => {
  const mic={source:{input_kind:'live_microphone'},song:{workflow_state:'REHEARSAL'},suspension_reasons:[],latest_frame:null};
  assert.equal(sourcePresentation(mic,false,null,'connecting').label,'Live Microphone · Connecting');
  assert.equal(sourcePresentation(mic,false,null,'disconnected').state,'disconnected');
  assert.equal(sourcePresentation({...mic,song:{workflow_state:'SUSPENDED'},suspension_reasons:['operator_paused']},true,null,'active').state,'suspended');
  assert.equal(sourcePresentation({...mic,song:{workflow_state:'ERROR'},suspension_reasons:['capture_failed']},true,null,'active').state,'error');
  const file={...mic,source:{input_kind:'uploaded_file'},latest_frame:{quality:{stale:false}}};
  assert.equal(sourcePresentation(file,true,1_000,'active',7_000).label,'Uploaded File · Stale');
  assert.equal(sourcePresentation(file,true,2_000,'active',3_000).label,'Uploaded File · Active');
  file.analysis_timing={receipt_max_age_s:12};
  assert.equal(sourcePresentation(file,true,2_000,'active',3_000,3_001).label,'Uploaded File · Active');
  assert.equal(sourcePresentation(file,true,2_000,'active',3_001,3_001).label,'Uploaded File · Stale');
});
test('reference preparation reports queued, progress, completion and failure honestly', () => {
  assert.equal(referenceProgressText({message:'Reference analysis queued.',progress:0}),'Reference analysis queued. · 0%');
  assert.equal(referenceProgressText({message:'Analyzing reference…',progress:.4}),'Analyzing reference… · 40%');
  assert.equal(referenceProgressText({message:'Reference analysis failed.',progress:1}),'Reference analysis failed. · 100%');
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
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ok:true,status:200,json:async()=>({record_type:'RehearsalProbeState',schema_version:'1.0',session_id:'new',state_version:1,mode:'idle',instrument_id:null,probe_id:null,not_before_monotonic_s:null})});
  try{
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
  }finally{
    globalThis.fetch=originalFetch;
  }
});
test('successful session commands reconcile server-canceled probe intent', async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  const probes = [];
  globalThis.fetch = async (url,options={}) => {
    urls.push(url);
    const payload = options.method === 'POST'
      ? {snapshot:{session_id:'s-1',state_version:2,event_sequence:2}}
      : {record_type:'RehearsalProbeState',schema_version:'1.0',session_id:'s-1',state_version:2,mode:'idle',instrument_id:null,probe_id:null,not_before_monotonic_s:null};
    return {ok:true,status:200,json:async()=>payload};
  };
  try{
    const adapter = new RuntimeAdapter({onSnapshot(){},onStatus(){},onProbe:value=>probes.push(value)});
    adapter.activateSession('s-1');
    adapter.acceptSnapshot({session_id:'s-1',state_version:1,event_sequence:1});
    await adapter.command({session_id:'s-1',action:'pause'});
    assert.deepEqual(urls,['/v1/sessions/s-1/actions','/v1/sessions/s-1/probes']);
    assert.equal(probes[0].mode,'idle');
  }finally{
    globalThis.fetch=originalFetch;
  }
});
test('runtime adapter refreshes probe intent once on state transitions and not on frame-only refreshes', async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  const probes = [];
  globalThis.fetch = async url => {
    urls.push(url);
    const payload = url.endsWith('/probes')
      ? {record_type:'RehearsalProbeState',schema_version:'1.0',session_id:'s-1',state_version:2,mode:'idle',instrument_id:null,probe_id:null,not_before_monotonic_s:null}
      : {session_id:'s-1',state_version:2,event_sequence:3};
    return {ok:true,status:200,json:async()=>payload};
  };
  try{
    const adapter = new RuntimeAdapter({onSnapshot(){},onStatus(){},onProbe:value=>probes.push(value)});
    adapter.activateSession('s-1');
    adapter.acceptSnapshot({session_id:'s-1',state_version:1,event_sequence:1});
    await adapter.handleEvent('s-1',{session_id:'s-1',event_sequence:2,payload:{record_type:'SessionSnapshot',session_id:'s-1',state_version:2,event_sequence:2}});
    await adapter.handleEvent('s-1',{session_id:'s-1',event_sequence:3,payload:{record_type:'AnalysisFrame'}});
    assert.deepEqual(urls,['/v1/sessions/s-1/probes','/v1/sessions/s-1']);
    assert.equal(probes.length,1);
    assert.equal(probes[0].mode,'idle');
  }finally{
    globalThis.fetch=originalFetch;
  }
});
test('delayed probe GET cannot overwrite newer same-session probe state', async () => {
  const originalFetch = globalThis.fetch;
  let resolveFetch;
  globalThis.fetch = async () => new Promise(resolve => { resolveFetch=resolve; });
  try{
    const seen=[];
    const adapter=new RuntimeAdapter({onSnapshot(){},onStatus(){},onProbe:value=>seen.push(value.state_version)});
    adapter.activateSession('s-1');
    adapter.acceptSnapshot({session_id:'s-1',state_version:6,event_sequence:6});
    const delayed=adapter.probeState('s-1');
    adapter.acceptSnapshot({session_id:'s-1',state_version:7,event_sequence:7});
    assert.equal(adapter.acceptProbe({record_type:'RehearsalProbeState',schema_version:'1.0',session_id:'s-1',state_version:7,mode:'idle',instrument_id:null,probe_id:null,not_before_monotonic_s:null}),true);
    resolveFetch({ok:true,status:200,json:async()=>({record_type:'RehearsalProbeState',schema_version:'1.0',session_id:'s-1',state_version:6,mode:'instrument',instrument_id:'guitar',probe_id:'old',not_before_monotonic_s:1})});
    await delayed;
    assert.equal(adapter.probe.state_version,7);
    assert.equal(adapter.probe.mode,'idle');
    assert.deepEqual(seen,[7]);
  }finally{
    globalThis.fetch=originalFetch;
  }
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
test('calibration bindings recover from no-frame, run/clock changes and explicit fresh retries', () => {
  const waiting={session_id:'s-1',source:{clock_id:'clock-1'},latest_frame:null};
  const empty=calibrationDraftFor(waiting);
  empty.acceptedBy='mei';
  empty.difference=true;
  assert.equal(empty.run,'');
  assert.equal(empty.start,null);
  const first={...waiting,latest_frame:{frame_id:'frame-1',analysis_run_id:'run-1',clock_id:'clock-1',sample_rate_hz:48000,sample_start:10,sample_end:20}};
  const hydrated=calibrationDraftFor(first,empty);
  assert.equal(hydrated.run,'run-1');
  assert.equal(hydrated.start,10);
  assert.equal(hydrated.acceptedBy,'mei');
  assert.equal(hydrated.difference,true);
  const laterSameRun={...first,latest_frame:{...first.latest_frame,frame_id:'frame-2',sample_start:30,sample_end:40}};
  assert.equal(calibrationDraftFor(laterSameRun,hydrated),hydrated);
  const retry=calibrationDraftFor(laterSameRun,hydrated,true);
  assert.equal(retry.frameId,'frame-2');
  assert.equal(retry.start,30);
  assert.equal(retry.acceptedBy,'mei');
  const nextRun={...first,source:{clock_id:'clock-2'},latest_frame:{...first.latest_frame,frame_id:'frame-3',analysis_run_id:'run-2',clock_id:'clock-2',sample_start:0,sample_end:48_000}};
  const rebound=calibrationDraftFor(nextRun,retry);
  assert.equal(rebound.run,'run-2');
  assert.equal(rebound.clock,'clock-2');
  assert.equal(rebound.start,0);
  assert.equal(rebound.acceptedBy,'mei');
});
test('catalog recovery tolerates corruption and preserves validated rehearsal counts', () => {
  assert.deepEqual(normalizeCatalogRows({broken:true}), []);
  const rows = normalizeCatalogRows([{session_id:'s-1',song_name:'Song',reference_id:7,baseline_id:null,instrument_counts:{guitar:2,evil:0,'bad family':3,bass:99}}]);
  assert.deepEqual(rows[0].instrument_counts, {guitar:2});
  assert.deepEqual(restoreConfiguredInstances(['guitar','drums'],rows[0]).map(x=>x.instrument_id), ['guitar-1','guitar-2','drums-1']);
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
  const progress = [];
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
    await adapter.setup({ project:'Demo', song:'Song', families:['guitar'], reference:{name:'reference.wav'}, source:'live_microphone', sourceId:'native-1', jobPollIntervalMs:0, onProgress:update=>progress.push(update) });
    const sessionBody = JSON.parse(requests.at(-1)[1].body);
    assert.deepEqual(sessionBody.source, { input_kind:'live_microphone', input_asset_or_device_id:'native-1' });
    assert.equal(sessionBody.capture_fingerprint.gain_setting, null);
    assert.equal(sessionBody.capture_fingerprint.enhancements_verified_disabled, null);
    assert.equal(sessionBody.capture_fingerprint.geometry_id, null);
    assert.equal(sessionBody.capture_fingerprint.provenance, 'unverified');
    assert.equal(sessionBody.capture_fingerprint.profile_id, 'ui-request-v1');
    assert.equal(sessionBody.capture_fingerprint.native_sample_rate_hz, 48000);
    assert.deepEqual(progress.filter(update=>update.stage==='reference').map(update=>update.status), ['queued','queued','completed']);
    assert.equal(progress.at(-1).message,'Rehearsal session ready.');
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.WebSocket = originalWebSocket;
    globalThis.location = originalLocation;
  }
});
test('reference job failure is surfaced and prevents session creation', async () => {
  const originalFetch=globalThis.fetch;
  const requests=[];
  const progress=[];
  const responses=[
    {project_id:'project-1'},
    {song_id:'song-1',supported_families:['bass'],unsupported_families:['guitar']},
    {asset_id:'asset-1'},
    {job_id:'job-1',status:'queued',progress:0,error:null},
    {job_id:'job-1',status:'failed',progress:1,error:'reference_decode_failed'},
  ];
  globalThis.fetch=async (url,options={})=>{requests.push([url,options]);return{ok:true,status:200,json:async()=>responses.shift()};};
  try{
    const adapter=new RuntimeAdapter({onSnapshot(){},onStatus(){}});
    await assert.rejects(()=>adapter.setup({project:'Demo',song:'Song',families:['guitar'],reference:{name:'reference.wav'},source:'uploaded_file',sourceId:'reference-asset',jobPollIntervalMs:0,onProgress:update=>progress.push(update)}),/reference_decode_failed/);
    assert.equal(requests.some(([url])=>url==='/v1/sessions'),false);
    assert.equal(progress.at(-1).status,'failed');
    assert.equal(progress.at(-1).error,'reference_decode_failed');
  }finally{globalThis.fetch=originalFetch;}
});
test('reference polling permits more than 400 authoritative progress updates before completion', async () => {
  const originalFetch=globalThis.fetch;
  const originalWebSocket=globalThis.WebSocket;
  const originalLocation=globalThis.location;
  const requests=[];
  const running=Array.from({length:450},(_,index)=>({job_id:'job-long',status:'running',progress:(index+1)/500,error:null}));
  const responses=[
    {project_id:'project-1'},
    {song_id:'song-1'},
    {asset_id:'asset-1'},
    {job_id:'job-long',status:'queued',progress:0,error:null},
    ...running,
    {job_id:'job-long',status:'completed',progress:1,error:null,reference_id:'reference-1'},
    {session_id:'session-long',state_version:0,event_sequence:0},
  ];
  globalThis.fetch=async(url,options={})=>{requests.push([url,options]);return{ok:true,status:200,json:async()=>responses.shift()};};
  globalThis.location={protocol:'http:',host:'127.0.0.1:8000'};
  globalThis.WebSocket=class{constructor(url){this.url=url;}close(){}};
  try{
    const progress=[];
    const adapter=new RuntimeAdapter({onSnapshot(){},onStatus(){}});
    const snapshot=await adapter.setup({project:'Demo',song:'Long reference',families:['bass'],reference:{name:'reference.wav'},source:'uploaded_file',sourceId:'reference-asset',jobPollIntervalMs:0,referenceJobRequestTimeoutMs:0,onProgress:update=>progress.push(update)});
    assert.equal(snapshot.session_id,'session-long');
    assert.equal(requests.filter(([url])=>url==='/v1/jobs/job-long').length,451);
    assert.equal(progress.filter(update=>update.stage==='reference').at(-1).status,'completed');
    adapter.stopEvents();
  }finally{
    globalThis.fetch=originalFetch;
    globalThis.WebSocket=originalWebSocket;
    globalThis.location=originalLocation;
  }
});
test('reference polling reports an explicit stall only after no authoritative movement', async () => {
  let clock=0;
  const updates=[];
  const responses=[
    {job_id:'job-stalled',status:'running',progress:.1,error:null},
    {job_id:'job-stalled',status:'running',progress:.1,error:null},
  ];
  await assert.rejects(
    ()=>pollReferenceJob(
      {job_id:'job-stalled',status:'queued',progress:0,error:null},
      {
        fetchJob:async()=>responses.shift(),
        onUpdate:update=>updates.push(update),
        pollIntervalMs:0,
        stallTimeoutMs:1000,
        requestTimeoutMs:0,
        sleep:async()=>{clock+=1000;},
        now:()=>clock,
      },
    ),
    /Reference analysis stalled \(job-stalled\): no Runtime progress update for 1 seconds\./,
  );
  assert.deepEqual(updates.map(update=>[update.status,update.progress]),[['running',.1],['running',.1]]);
});
test('reference polling reports a hung Runtime status request explicitly', async () => {
  await assert.rejects(
    ()=>pollReferenceJob(
      {job_id:'job-dead',status:'running',progress:.1,error:null},
      {fetchJob:async()=>new Promise(()=>{}),pollIntervalMs:0,stallTimeoutMs:60_000,requestTimeoutMs:1},
    ),
    /Reference analysis status request timed out \(job-dead\)\./,
  );
});
test('replacement session reuses retained song/reference/source but never copies physical provenance claims', async () => {
  const originalFetch = globalThis.fetch;
  const originalWebSocket = globalThis.WebSocket;
  const originalLocation = globalThis.location;
  const requests = [];
  globalThis.fetch = async (url, options={}) => {
    requests.push([url,options]);
    return {ok:true,status:200,json:async()=>({session_id:'replacement-1',state_version:0,event_sequence:0})};
  };
  globalThis.location = {protocol:'http:',host:'127.0.0.1:8000'};
  globalThis.WebSocket = class { constructor(url){this.url=url;} close(){} };
  try{
    const adapter = new RuntimeAdapter({onSnapshot(){},onStatus(){}});
    adapter.activateSession('old-1');
    await adapter.recreateSession({
      song:{song_id:'song-1'},active_reference:{reference_id:'reference-1'},
      source:{input_kind:'live_microphone',input_asset_or_device_id:'portaudio:1'},
      active_baseline:{capture:{profile_id:'capture-1',native_sample_rate_hz:44100,provenance:'physical_verified',gain_setting:'fixed',geometry_id:'secret-geometry'}},
    });
    const body=JSON.parse(requests[0][1].body);
    assert.equal(body.song_id,'song-1');
    assert.equal(body.reference_id,'reference-1');
    assert.deepEqual(body.source,{input_kind:'live_microphone',input_asset_or_device_id:'portaudio:1'});
    assert.equal(body.capture_fingerprint.profile_id,'capture-1');
    assert.equal(body.capture_fingerprint.native_sample_rate_hz,44100);
    assert.equal(body.capture_fingerprint.provenance,'unverified');
    assert.equal(body.capture_fingerprint.gain_setting,null);
    assert.equal(body.capture_fingerprint.geometry_id,null);
  }finally{
    globalThis.fetch=originalFetch;
    globalThis.WebSocket=originalWebSocket;
    globalThis.location=originalLocation;
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
  assert.match(source, /Listening against your reference/);
  assert.match(source, /function button\(text,fn,cls='primary',type='button'\)/);
  assert.match(source, /runtimeAdapter\?\.stopEvents\(\)/);
  assert.match(source, /operationStatus=text/);
  assert.match(source, /live-shell-input/);
  assert.match(source, /setupRows=\[\['guitar',2\],\['vocals',1\]/);
  assert.doesNotMatch(source, /\['vocal',1\]/);
  assert.match(source, /\['keys',0\]/);
  assert.doesNotMatch(source, /Requested sample rate/);
  assert.match(source, /Prepare reference/);
  assert.match(source, /setupLiveReference/);
  assert.doesNotMatch(source, /function renderCalibration|function renderRehearsal|function acceptBaseline/);
});
test('responsive evidence rows support variable counts without fixed four-card selectors', async () => {
  const css = await readFile(new URL('../../apps/ui/styles.css', import.meta.url), 'utf8');
  assert.match(css, /\.instrument-grid\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column/s);
  assert.match(css, /\.instrument-card\s*\{[^}]*grid-template-areas:/s);
  assert.match(css, /@media\s*\(max-width:\s*980px\)[\s\S]*\.instrument-card\s*\{/);
  assert.match(css, /\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}/);
  assert.doesNotMatch(css, /nth-child\(4\)/);
});

test('Harmonix visual tokens stay restrained and free of decorative effects', async () => {
  const css = await readFile(new URL('../../apps/ui/styles.css', import.meta.url), 'utf8');
  const app = await readFile(new URL('../../apps/ui/app.js', import.meta.url), 'utf8');
  assert.match(css, /--charcoal:\s*#1a1a1a/i);
  assert.match(css, /--slate:\s*#334155/i);
  assert.match(css, /--harmonix-blue:\s*#4f7ca8/i);
  assert.match(css, /--stone:\s*#d9dbe0/i);
  assert.match(css, /--off-white:\s*#f7f6f3/i);
  assert.doesNotMatch(css, /radial-gradient|repeating-(?:linear|radial)-gradient|box-shadow|border-radius:\s*999px/i);
  assert.doesNotMatch(css, /#070b27|#3ee29d|#2fbd4d/i);
  assert.match(app, /'Harmonix','brand'/);
  assert.match(app, /'REFERENCE'/);
  assert.match(app, /'CURRENT STATE'/);
  assert.match(app, /'SUGGESTED FIX'/);
});
