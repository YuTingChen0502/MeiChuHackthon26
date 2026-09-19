const FIXTURE_PATH = '../../contracts/examples/pa_shared_v1.json';

export const SETUP_ENDPOINT_PLAN = [
  'POST /v1/projects  — project and setlist metadata',
  'POST /v1/songs  — song and declared instrument families',
  'POST /v1/audio-assets  — upload mixed audio bytes',
  'POST /v1/songs/{id}/reference  — associate asset; receive job ID',
  'GET /v1/jobs/{id}  — await reference profile',
  'POST /v1/sessions  — choose rehearsal/file/live source and profile IDs',
];

export function displayStatus(instrument) {
  if (instrument.activity === 'inactive') return instrument.confidence.abstained ? 'Inactive · Abstained' : 'Inactive';
  if (instrument.activity === 'unsupported' || instrument.status === 'unsupported') return instrument.confidence.abstained ? 'Unsupported · Abstained' : 'Unsupported';
  if (instrument.activity === 'unknown' || instrument.status === 'unknown') return instrument.confidence.abstained ? 'Unknown / Not Observable · Abstained' : 'Unknown / Not Observable';
  if (instrument.confidence.abstained) return 'Abstained / Unknown';
  return ({ normal: 'Normal', too_loud: 'Too Loud', too_quiet: 'Too Quiet' })[instrument.status] || 'Not Observable';
}

export function balanceText(instrument) {
  const usable = !instrument.confidence.abstained && instrument.activity === 'active' &&
    ['normal', 'too_loud', 'too_quiet'].includes(instrument.status) &&
    typeof instrument.balance_deviation_db === 'number';
  return usable ? `About ${instrument.balance_deviation_db >= 0 ? '+' : ''}${instrument.balance_deviation_db.toFixed(1)} dB balance` : 'Balance unavailable';
}

export function freshness(frame, authoritativeNowMonotonicS = null) {
  if (!frame) return 'No observation received';
  if (frame.quality.stale) return frame.example_only ? 'Stale fixture frame — do not act' : 'Stale frame — do not act';
  if (typeof authoritativeNowMonotonicS !== 'number') return frame.example_only ? 'Fixture/static frame — data age unavailable' : 'Data age unavailable';
  const age = Math.max(0, authoritativeNowMonotonicS - frame.published_monotonic_s);
  return `${age.toFixed(1)} s old`;
}

export function commandFor(snapshot, action, payload = {}, idempotencyKey = `ui-${action}-fixture`) {
  const reference = snapshot.active_reference && { reference_id: snapshot.active_reference.reference_id, source_asset_hash: snapshot.active_reference.source_asset_hash };
  const baseline = snapshot.active_baseline && { baseline_id: snapshot.active_baseline.baseline_id, baseline_version: snapshot.active_baseline.version };
  const event = snapshot.incident && { event_id: snapshot.incident.event.event_id, event_version: snapshot.incident.event_version };
  return { record_type: 'SessionCommand', schema_version: '1.0', session_id: snapshot.session_id,
    idempotency_key: idempotencyKey, expected_state_version: snapshot.state_version,
    reference, baseline, event, action, payload };
}

export function confidenceText(confidence) {
  const calibration = confidence.calibration_status.replaceAll('_', ' ');
  if (confidence.abstained) return `Abstained · ${calibration}: ${confidence.reasons.join(', ')}`;
  const probability = confidence.probability === null ? 'Probability unavailable' :
    `${Math.round(confidence.probability * 100)}% probability of ${confidence.probability_event.replaceAll('_', ' ')}`;
  const tolerance = `Magnitude tolerance: ±${confidence.magnitude_tolerance_db} dB`;
  const interval = confidence.prediction_interval_db === null ? null :
    `Prediction interval: ${confidence.prediction_interval_db[0]} to ${confidence.prediction_interval_db[1]} dB`;
  return [calibration, probability, tolerance, interval].filter(Boolean).join(' · ');
}

function showcaseFrame(snapshot, fixtureMode = 'live') {
  const makeConfidence = (abstained, reasons, probability = .91) => ({ record_type:'ConfidenceState', schema_version:'1.0', calibration_status: abstained ? 'out_of_envelope':'calibrated', calibration_id: abstained ? null:'fixture-calibration', probability_event: abstained ? 'not_available':'joint_anomaly_numeric_correct', magnitude_tolerance_db: 1.5, probability: abstained ? null:probability, prediction_interval_db: abstained ? null:[-1.1,1.2], abstained, reasons });
  const item = (instrument_id, activity, status, deviation, confidence) => ({ record_type:'InstrumentState', schema_version:'1.0', instrument_id, family:instrument_id, activity, presence_probability:activity === 'active' ? .92:null, source_level_delta_db:deviation, balance_deviation_db:deviation, status, confidence, tone:null });
  return { record_type:'AnalysisFrame', schema_version:'1.0', example_only:true, frame_id:'fixture-frame-operator', session_id:snapshot.session_id, analysis_run_id:'fixture-run-operator', sequence:9, input_kind:snapshot.source.input_kind, input_asset_or_device_id:snapshot.source.input_asset_or_device_id, clock_id:snapshot.source.clock_id, sample_rate_hz:48000, sample_start:2016000, sample_end:2208000, capture_end_monotonic_s:46, published_monotonic_s:47, model_bundle_id:snapshot.execution.model_bundle_id, frontend_id:snapshot.execution.frontend_id, execution_profile_id:snapshot.execution.execution_profile_id, baseline_id:snapshot.active_baseline?.baseline_id ?? null, baseline_version:snapshot.active_baseline?.version ?? null, reference_id:snapshot.active_reference.reference_id, quality:{clipped_fraction:0,dropout:false,stale:false,comparability:'comparable',capture_compatible:true,reason_codes:[],snr_estimate_db:null,snr_is_ground_truth:false}, observed_mix_level_delta_db:.2,common_mode_gain_db:.1,identifiability_assumption:'majority_active_sources_unchanged',inference_wall_ms:28,
    instruments: fixtureMode === 'rehearsal' ? [item('guitar','active','normal',.2,makeConfidence(false,[],.92)), item('bass','inactive','inactive',null,makeConfidence(true,['source_inactive'])), item('drums','unknown','unknown',null,makeConfidence(true,['noise_overlap','not_observable']))] : [item('guitar','active','too_loud',4.1,makeConfidence(false,[],.92)), item('bass','active','normal',.2,makeConfidence(false,[],.88)), item('drums','inactive','inactive',null,makeConfidence(true,['source_inactive']))] };
}

export function fixtureScenario(base) {
  const snapshot = structuredClone(base.live_snapshot);
  snapshot.latest_frame = showcaseFrame(snapshot);
  snapshot.incident_state = 'active'; snapshot.song.workflow_state = 'LIVE_ANOMALY';
  const target = { target_kind:'baseline', reference:{reference_id:snapshot.active_reference.reference_id,source_asset_hash:snapshot.active_reference.source_asset_hash}, baseline:{baseline_id:snapshot.active_baseline.baseline_id,baseline_version:snapshot.active_baseline.version} };
  const event = { record_type:'AnomalyEvent', schema_version:'1.0', event_id:'fixture-event-1', session_id:snapshot.session_id, instrument_ids:['guitar'], direction:'too_loud', onset_monotonic_s:43, confirmed_monotonic_s:46, baseline_id:snapshot.active_baseline.baseline_id, reference_id:snapshot.active_reference.reference_id, evidence_frame_ids:[snapshot.latest_frame.frame_id], state:'active', confidence:snapshot.latest_frame.instruments[0].confidence };
  snapshot.incident = { event, event_version:1, target };
  snapshot.recommendations = [{ record_type:'Recommendation', schema_version:'1.0', recommendation_id:'fixture-recommendation-1', event_id:event.event_id, instrument_id:'guitar', action:'reduce_level', suggested_step_db:-3, human_control_hint:'Make a small manual guitar-level correction, then recheck.', message_template_id:'reduce-level-v1', evidence_frame_ids:[snapshot.latest_frame.frame_id], expires_monotonic_s:60, automatic_execution:false }];
  snapshot.latest_verification = { record_type:'VerificationResult', schema_version:'1.0', verification_id:'fixture-verification-1', event_id:event.event_id, adjustment_id:'fixture-adjustment-1', baseline_id:snapshot.active_baseline.baseline_id, baseline_version:snapshot.active_baseline.version, adjustment_completed_monotonic_s:47, first_evidence_sample_start_monotonic_s:48, evidence_frame_ids:[], instrument_id:'guitar', before_balance_db:4.1, after_balance_db:null, source_observable:false, outcome:'inconclusive', reason_codes:['awaiting_post_adjustment_audio'] };
  return snapshot;
}

export function fixtureRehearsal(base) {
  const snapshot = structuredClone(base.rehearsal_snapshot);
  snapshot.latest_frame = showcaseFrame(snapshot, 'rehearsal');
  return snapshot;
}

function render(snapshot) {
  const frame = snapshot.latest_frame;
  document.querySelector('#mode').textContent = `${snapshot.session_mode === 'live' ? 'LIVE' : 'REHEARSAL'} · ${snapshot.incident_state}`;
  document.querySelector('#summary').innerHTML = `<div><span class="eyebrow">SONG / SESSION</span><strong>${snapshot.song.name} · ${snapshot.session_id}</strong></div><div><span class="eyebrow">CAPTURE</span><strong>${snapshot.source.input_kind.replaceAll('_',' ')} · ${snapshot.source.input_asset_or_device_id}</strong></div><div><span class="eyebrow">RUNTIME</span><strong>${snapshot.execution.provider} · ${snapshot.execution.model_bundle_id}</strong></div>`;
  document.querySelector('#profiles').innerHTML = `<div><p class="profile-name">IDEAL REFERENCE</p><strong>${snapshot.active_reference?.reference_id ?? 'Not ready'}</strong><p class="muted">Immutable uploaded mixed reference</p></div><div><p class="profile-name">ACCEPTED BASELINE</p><strong>${snapshot.active_baseline ? `${snapshot.active_baseline.baseline_id} v${snapshot.active_baseline.version}` : 'Not accepted'}</strong><p class="muted">Human acceptance only; never automatic</p></div>`;
  document.querySelector('#freshness').textContent = freshness(frame);
  document.querySelector('#instrument-cards').innerHTML = (frame?.instruments ?? []).map(i => `<article class="instrument ${i.status}"><span class="status ${i.status}">${displayStatus(i)}</span><h3>${i.family}</h3><p class="metric">${balanceText(i)}</p><p class="muted">${confidenceText(i.confidence)}</p></article>`).join('') || '<p class="muted">Awaiting analysis frame.</p>';
  const rec = snapshot.recommendations?.[0];
  document.querySelector('#recommendation').innerHTML = rec ? `<strong>${rec.instrument_id}: ${rec.action.replaceAll('_',' ')}</strong><p>${rec.human_control_hint}</p><p class="muted">${rec.suggested_step_db === null ? 'No numeric step is available.' : `Suggested bounded step: ${rec.suggested_step_db} dB`} · Human executes; automatic execution is false.</p>` : '<p class="muted">No current recommendation.</p>';
  const verification = snapshot.latest_verification;
  document.querySelector('#verification').innerHTML = verification ? `<strong class="${verification.outcome === 'recovered' ? '' : 'negative'}">${verification.outcome.replaceAll('_',' ')}</strong><p class="muted">${verification.source_observable ? 'Post-adjustment source was observable.' : 'No recovery claim: fresh, observable post-adjustment audio is still required.'}</p><p class="muted">${verification.reason_codes.join(', ')}</p>` : '<p class="muted">No verification result yet.</p>';
  renderControls(snapshot);
}

function renderControls(snapshot) {
  const recheckPayload = { adjustment_id: snapshot.adjustment?.adjustment_id ?? null };
  const acceptPayload = { interval:{ analysis_run_id:snapshot.latest_frame?.analysis_run_id ?? 'unavailable', clock_id:snapshot.source.clock_id, sample_rate_hz:snapshot.latest_frame?.sample_rate_hz ?? 48000, sample_start:snapshot.latest_frame?.sample_start ?? 0, sample_end:snapshot.latest_frame?.sample_end ?? 0 }, accepted_by:'operator', reference_difference_accepted:true, acceptance_note:null };
  const actions = [ ['recheck','Recheck',recheckPayload,false], ['accept_baseline','Accept as Baseline',acceptPayload, snapshot.session_mode !== 'rehearsal'], ['start_adjustment','Start adjustment',{},false], ['complete_adjustment','Complete adjustment',{ adjustment_id:snapshot.adjustment?.adjustment_id ?? 'unavailable' },!snapshot.adjustment], ['start_live','Enter Live',{},!snapshot.active_baseline], ['pause','Pause',{},false], ['stop','Stop session',{},false] ];
  document.querySelector('#controls').innerHTML = actions.map(([action,label,payload,disabled]) => `<button data-action="${action}" ${disabled ? 'disabled' : ''}>${label}</button>`).join('');
  document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => {
    const entry = actions.find(([action]) => action === button.dataset.action);
    const command = commandFor(snapshot, entry[0], entry[2], `fixture-${entry[0]}-${crypto.randomUUID()}`);
    document.querySelector('#command-status').textContent = `Fixture adapter prepared ${command.action}; real submission waits for the Runtime-owned command handler. State bindings are included in the command.`;
    console.info('PA fixture command (not sent)', command);
  }));
}

async function start() {
  const response = await fetch(FIXTURE_PATH);
  const fixtures = await response.json();
  const liveSnapshot = fixtureScenario(fixtures);
  const rehearsalSnapshot = fixtureRehearsal(fixtures);
  let snapshot = liveSnapshot;
  render(snapshot);
  document.querySelector('#fixture-live').addEventListener('click', () => { snapshot = liveSnapshot; render(snapshot); });
  document.querySelector('#fixture-rehearsal').addEventListener('click', () => { snapshot = rehearsalSnapshot; render(snapshot); });
  document.querySelector('#show-setup').addEventListener('click', () => { const plan = document.querySelector('#setup-plan'); plan.hidden = !plan.hidden; plan.textContent = SETUP_ENDPOINT_PLAN.join('\n'); });
  document.querySelector('#setup-form').addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const reference = data.get('reference');
    const selected = { project:data.get('project'), song:data.get('song'), families:data.get('families').split(',').map(value => value.trim()).filter(Boolean), reference_file:reference?.name || null, source:data.get('source') };
    const plan = document.querySelector('#setup-plan');
    plan.hidden = false;
    plan.textContent = `${SETUP_ENDPOINT_PLAN.join('\n')}\n\nFixture request parameters (not sent):\n${JSON.stringify(selected, null, 2)}`;
  });
}

if (typeof document !== 'undefined') start().catch(error => { document.body.innerHTML = `<p>Could not load frozen fixtures: ${error.message}</p>`; });
