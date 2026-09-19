import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { balanceText, commandFor, confidenceText, displayStatus, fixtureRehearsal, fixtureScenario, freshness, SETUP_ENDPOINT_PLAN } from '../../apps/ui/app.js';

const confidence = (abstained = false) => ({ abstained, reasons: abstained ? ['noise_overlap'] : [], calibration_status: abstained ? 'out_of_envelope' : 'calibrated', probability: abstained ? null : .9, magnitude_tolerance_db: 1.5 });
const active = (status, balance, c = confidence()) => ({ activity:'active', status, balance_deviation_db:balance, confidence:c });

test('shows numeric balance only for valid active non-abstained states', () => {
  assert.equal(balanceText(active('too_loud', 4.1)), 'About +4.1 dB balance');
  assert.equal(balanceText(active('normal', 0)), 'About +0.0 dB balance');
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
test('derived fixture frames only contain declared families and correct profile bindings', async () => {
  const fixtures = JSON.parse(await readFile(new URL('../../contracts/examples/pa_shared_v1.json', import.meta.url)));
  for (const snapshot of [fixtureScenario(fixtures), fixtureRehearsal(fixtures)]) {
    const declared = new Set(snapshot.song.configured_families);
    assert.deepEqual(new Set(snapshot.latest_frame.instruments.map(item => item.instrument_id)), declared);
    assert.equal(snapshot.latest_frame.session_id, snapshot.session_id);
    assert.equal(snapshot.latest_frame.reference_id, snapshot.active_reference.reference_id);
    assert.equal(snapshot.latest_frame.baseline_id, snapshot.active_baseline?.baseline_id ?? null);
  }
});
