import { RuntimeAdapter } from './runtime-adapter.js';

const FIXTURE_PATH = '../../contracts/examples/pa_shared_v1.json';
let runtimeAdapter = null;

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
  const makeConfidence = (abstained, reasons, probability = .91, probabilityEvent = 'joint_anomaly_numeric_correct', interval = [2.6, 5.6]) => ({ record_type:'ConfidenceState', schema_version:'1.0', calibration_status: abstained ? 'out_of_envelope':'calibrated', calibration_id: abstained ? null:'fixture-calibration', probability_event: abstained ? 'not_available':probabilityEvent, magnitude_tolerance_db: 1.5, probability: abstained ? null:probability, prediction_interval_db: abstained ? null:interval, abstained, reasons });
  const item = (instrument_id, activity, status, deviation, confidence) => ({ record_type:'InstrumentState', schema_version:'1.0', instrument_id, family:instrument_id, activity, presence_probability:activity === 'active' ? .92:null, source_level_delta_db:deviation, balance_deviation_db:deviation, status, confidence, tone:null });
  return { record_type:'AnalysisFrame', schema_version:'1.0', example_only:true, frame_id:'fixture-frame-operator', session_id:snapshot.session_id, analysis_run_id:'fixture-run-operator', sequence:9, input_kind:snapshot.source.input_kind, input_asset_or_device_id:snapshot.source.input_asset_or_device_id, clock_id:snapshot.source.clock_id, sample_rate_hz:48000, sample_start:2016000, sample_end:2208000, capture_end_monotonic_s:46, published_monotonic_s:47, model_bundle_id:snapshot.execution.model_bundle_id, frontend_id:snapshot.execution.frontend_id, execution_profile_id:snapshot.execution.execution_profile_id, baseline_id:snapshot.active_baseline?.baseline_id ?? null, baseline_version:snapshot.active_baseline?.version ?? null, reference_id:snapshot.active_reference.reference_id, quality:{clipped_fraction:0,dropout:false,stale:false,comparability:'comparable',capture_compatible:true,reason_codes:[],snr_estimate_db:null,snr_is_ground_truth:false}, observed_mix_level_delta_db:.2,common_mode_gain_db:.1,identifiability_assumption:'majority_active_sources_unchanged',inference_wall_ms:28,
    instruments: fixtureMode === 'rehearsal' ? [item('guitar','active','normal',.2,makeConfidence(false,[],.92,'normal_within_envelope',[-1.3, 1.5])), item('bass','inactive','inactive',null,makeConfidence(true,['source_inactive'])), item('drums','unknown','unknown',null,makeConfidence(true,['noise_overlap','not_observable']))] : [item('guitar','active','too_loud',4.1,makeConfidence(false,[],.92,'joint_anomaly_numeric_correct',[2.6, 5.6])), item('bass','active','normal',.2,makeConfidence(false,[],.88,'normal_within_envelope',[-1.3, 1.5])), item('drums','inactive','inactive',null,makeConfidence(true,['source_inactive']))] };
}

export function fixtureScenario(base) {
  const snapshot = structuredClone(base.live_snapshot);
  snapshot.latest_frame = showcaseFrame(snapshot);
  snapshot.incident_state = 'active'; snapshot.song.workflow_state = 'LIVE_ANOMALY';
  const target = { target_kind:'baseline', reference:{reference_id:snapshot.active_reference.reference_id,source_asset_hash:snapshot.active_reference.source_asset_hash}, baseline:{baseline_id:snapshot.active_baseline.baseline_id,baseline_version:snapshot.active_baseline.version} };
  const event = { record_type:'AnomalyEvent', schema_version:'1.0', event_id:'fixture-event-1', session_id:snapshot.session_id, instrument_ids:['guitar'], direction:'too_loud', onset_monotonic_s:43, confirmed_monotonic_s:46, baseline_id:snapshot.active_baseline.baseline_id, reference_id:snapshot.active_reference.reference_id, evidence_frame_ids:[snapshot.latest_frame.frame_id], state:'active', confidence:snapshot.latest_frame.instruments[0].confidence };
  snapshot.incident = { event, event_version:1, target };
  snapshot.recommendations = [{ record_type:'Recommendation', schema_version:'1.0', recommendation_id:'fixture-recommendation-1', event_id:event.event_id, instrument_id:'guitar', action:'reduce_level', suggested_step_db:-2, human_control_hint:'Make a small manual guitar-level correction, then recheck.', message_template_id:'reduce-level-v1', evidence_frame_ids:[snapshot.latest_frame.frame_id], expires_monotonic_s:60, automatic_execution:false }];
  snapshot.latest_verification = { record_type:'VerificationResult', schema_version:'1.0', verification_id:'fixture-verification-1', event_id:event.event_id, adjustment_id:'fixture-adjustment-1', baseline_id:snapshot.active_baseline.baseline_id, baseline_version:snapshot.active_baseline.version, adjustment_completed_monotonic_s:47, first_evidence_sample_start_monotonic_s:48, evidence_frame_ids:[], instrument_id:'guitar', before_balance_db:4.1, after_balance_db:null, source_observable:false, outcome:'inconclusive', reason_codes:['awaiting_post_adjustment_audio'] };
  return snapshot;
}

export function fixtureRehearsal(base) {
  const snapshot = structuredClone(base.rehearsal_snapshot);
  snapshot.latest_frame = showcaseFrame(snapshot, 'rehearsal');
  return snapshot;
}

function node(tag, text, className = '') {
  const result = document.createElement(tag);
  result.textContent = text;
  if (className) result.className = className;
  return result;
}

function summaryItem(label, value) {
  const container = document.createElement('div');
  container.append(node('span', label, 'eyebrow'), node('strong', value));
  return container;
}

function profileItem(label, value, detail) {
  const container = document.createElement('div');
  container.append(node('p', label, 'profile-name'), node('strong', value), node('p', detail, 'muted'));
  return container;
}

function render(snapshot) {
  const frame = snapshot.latest_frame;
  document.querySelector('#mode').textContent = `${snapshot.session_mode === 'live' ? 'LIVE' : 'REHEARSAL'} · ${snapshot.incident_state}`;
  document.querySelector('#summary').replaceChildren(
    summaryItem('SONG / SESSION', `${snapshot.song.name} · ${snapshot.session_id}`),
    summaryItem('CAPTURE', `${snapshot.source.input_kind.replaceAll('_',' ')} · ${snapshot.source.input_asset_or_device_id}`),
    summaryItem('RUNTIME', `${snapshot.execution.provider} · ${snapshot.execution.model_bundle_id}`),
  );
  document.querySelector('#profiles').replaceChildren(
    profileItem('IDEAL REFERENCE', snapshot.active_reference?.reference_id ?? 'Not ready', 'Immutable uploaded mixed reference'),
    profileItem('ACCEPTED BASELINE', snapshot.active_baseline ? `${snapshot.active_baseline.baseline_id} v${snapshot.active_baseline.version}` : 'Not accepted', 'Human acceptance only; never automatic'),
  );
  document.querySelector('#freshness').textContent = freshness(frame);
  const cards = (frame?.instruments ?? []).map(instrument => {
    const card = document.createElement('article');
    const stateClass = ['normal', 'too_loud', 'too_quiet', 'unknown', 'inactive', 'unsupported'].includes(instrument.status) ? instrument.status : 'unknown';
    card.className = `instrument ${stateClass}`;
    card.append(node('span', displayStatus(instrument), `status ${stateClass}`), node('h3', instrument.family), node('p', balanceText(instrument), 'metric'), node('p', confidenceText(instrument.confidence), 'muted'));
    return card;
  });
  document.querySelector('#instrument-cards').replaceChildren(...(cards.length ? cards : [node('p', 'Awaiting analysis frame.', 'muted')]));
  const rec = snapshot.recommendations?.[0];
  const recommendation = document.querySelector('#recommendation');
  const expired = rec && frame && rec.expires_monotonic_s <= frame.published_monotonic_s;
  recommendation.replaceChildren(...(!rec ? [node('p', 'No current recommendation.', 'muted')] : expired ? [node('strong', 'Recommendation expired', 'negative'), node('p', 'Do not act on expired recommendation data.', 'muted')] : [node('strong', `${rec.instrument_id}: ${rec.action.replaceAll('_',' ')}`), node('p', rec.human_control_hint ?? 'No operator hint supplied.'), node('p', `${rec.suggested_step_db === null ? 'No numeric step is available.' : `Suggested bounded step: ${rec.suggested_step_db} dB`} · Human executes; automatic execution is false. Expires at session t=${rec.expires_monotonic_s}s.`, 'muted')]));
  const verification = snapshot.latest_verification;
  const verificationPanel = document.querySelector('#verification');
  verificationPanel.replaceChildren(...(!verification ? [node('p', 'No verification result yet.', 'muted')] : [node('strong', verification.outcome.replaceAll('_',' '), verification.outcome === 'recovered' ? '' : 'negative'), node('p', verification.source_observable ? 'Post-adjustment source was observable.' : 'No recovery claim: fresh, observable post-adjustment audio is still required.', 'muted'), node('p', verification.reason_codes.join(', '), 'muted')]));
  renderControls(snapshot);
}

function renderControls(snapshot) {
  const recheckPayload = { adjustment_id: snapshot.adjustment?.adjustment_id ?? null };
  const qualified = document.querySelector('#qualified-interval').checked;
  const differenceChoice = document.querySelector('input[name="reference-difference"]:checked')?.value;
  const acceptedBy = document.querySelector('#accepted-by').value.trim();
  const interval = { analysis_run_id:document.querySelector('#acceptance-run').value.trim(), clock_id:snapshot.source.clock_id, sample_rate_hz:Number(document.querySelector('#acceptance-rate').value), sample_start:Number(document.querySelector('#acceptance-start').value), sample_end:Number(document.querySelector('#acceptance-end').value) };
  const acceptPayload = { interval, accepted_by:acceptedBy, reference_difference_accepted:differenceChoice === 'true', acceptance_note:null };
  const acceptanceReady = qualified && differenceChoice !== undefined && acceptedBy.length > 0 && interval.analysis_run_id && Number.isInteger(interval.sample_rate_hz) && interval.sample_rate_hz > 0 && Number.isInteger(interval.sample_start) && Number.isInteger(interval.sample_end) && interval.sample_start >= 0 && interval.sample_end > interval.sample_start;
  const actions = [ ['recheck','Recheck',recheckPayload,false], ['accept_baseline','Accept as Baseline',acceptPayload, snapshot.session_mode !== 'rehearsal' || !acceptanceReady], ['start_adjustment','Start adjustment',{},false], ['complete_adjustment','Complete adjustment',{ adjustment_id:snapshot.adjustment?.adjustment_id ?? 'unavailable' },!snapshot.adjustment], ['start_live','Enter Live',{},!snapshot.active_baseline], ['pause','Pause',{},false], ['resume','Resume',{},false], ['stop','Stop session',{},false] ];
  const controlPanel = document.querySelector('#controls');
  controlPanel.replaceChildren(...actions.map(([action, label, payload, disabled]) => {
    const button = node('button', label);
    button.disabled = disabled;
    button.addEventListener('click', () => {
      const command = commandFor(snapshot, action, payload, `${runtimeAdapter ? 'ui' : 'fixture'}-${action}-${crypto.randomUUID()}`);
      if (!runtimeAdapter) {
        document.querySelector('#command-status').textContent = `Fixture adapter prepared ${command.action}; Runtime is not connected.`;
        return;
      }
      runtimeAdapter.command(command).then(() => {
        document.querySelector('#command-status').textContent = `${command.action} accepted by Runtime.`;
      }).catch(error => {
        document.querySelector('#command-status').textContent = `Runtime rejected ${command.action}: ${error.message}`;
      });
    });
    return button;
  }));
}

async function start() {
  const response = await fetch(FIXTURE_PATH);
  const fixtures = await response.json();
  const liveSnapshot = fixtureScenario(fixtures);
  const rehearsalSnapshot = fixtureRehearsal(fixtures);
  let snapshot = liveSnapshot;
  render(snapshot);
  const adapter = new RuntimeAdapter({
    onSnapshot(next) { snapshot = next; render(snapshot); },
    onStatus(message) { document.querySelector('#command-status').textContent = message; },
  });
  try {
    await adapter.health();
    runtimeAdapter = adapter;
    document.querySelector('#source-mode').textContent = 'Local Runtime connected. Live records are authoritative; fixture buttons remain illustrative.';
    document.querySelector('#command-status').textContent = 'Local Runtime available. Complete setup to start an authoritative session.';
  } catch {
    document.querySelector('#command-status').textContent = 'Fixture mode: local Runtime is unavailable.';
  }
  document.querySelector('#fixture-live').addEventListener('click', () => { snapshot = liveSnapshot; render(snapshot); });
  document.querySelector('#fixture-rehearsal').addEventListener('click', () => { snapshot = rehearsalSnapshot; render(snapshot); });
  document.querySelector('#baseline-acceptance').addEventListener('input', () => renderControls(snapshot));
  document.querySelector('#show-setup').addEventListener('click', () => { const plan = document.querySelector('#setup-plan'); plan.hidden = !plan.hidden; plan.textContent = SETUP_ENDPOINT_PLAN.join('\n'); });
  document.querySelector('#setup-form').addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const reference = data.get('reference');
    const selected = { project:data.get('project'), song:data.get('song'), families:data.get('families').split(',').map(value => value.trim()).filter(Boolean), reference, source:data.get('source'), sourceId:data.get('sourceId'), captureProfile:data.get('captureProfile'), geometryId:data.get('geometryId') };
    const plan = document.querySelector('#setup-plan');
    if (runtimeAdapter) {
      if (!(reference instanceof File)) { document.querySelector('#command-status').textContent = 'Choose a PCM16 WAV ideal reference before setup.'; return; }
      document.querySelector('#command-status').textContent = 'Creating project, song, reference profile, and rehearsal session…';
      runtimeAdapter.setup(selected).then(() => { document.querySelector('#command-status').textContent = 'Authoritative rehearsal session created.'; }).catch(error => { document.querySelector('#command-status').textContent = `Setup failed: ${error.message}`; });
      return;
    }
    plan.hidden = false;
    plan.textContent = `${SETUP_ENDPOINT_PLAN.join('\n')}\n\nFixture request plan only; Runtime is not connected.`;
  });
}

if (typeof document !== 'undefined') start().catch(error => { document.body.replaceChildren(node('p', `Could not load frozen fixtures: ${error.message}`)); });
