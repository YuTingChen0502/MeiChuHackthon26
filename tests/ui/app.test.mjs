import assert from 'node:assert/strict';
import test from 'node:test';
import { balanceText, commandFor, displayStatus, freshness, SETUP_ENDPOINT_PLAN } from '../../apps/ui/app.js';

const confidence = (abstained = false) => ({ abstained, reasons: abstained ? ['noise_overlap'] : [], calibration_status: abstained ? 'out_of_envelope' : 'calibrated', probability: abstained ? null : .9, magnitude_tolerance_db: 1.5 });
const active = (status, balance, c = confidence()) => ({ activity:'active', status, balance_deviation_db:balance, confidence:c });

test('shows numeric balance only for valid active non-abstained states', () => {
  assert.equal(balanceText(active('too_loud', 4.1)), 'About +4.1 dB balance');
  assert.equal(balanceText(active('normal', 0)), 'About +0.0 dB balance');
  assert.equal(balanceText(active('unknown', null, confidence(true))), 'Balance unavailable');
});
test('renders explicit inactive and abstained states', () => {
  assert.equal(displayStatus({ activity:'inactive', status:'inactive', confidence:confidence(true) }), 'Abstained / Unknown');
  assert.equal(displayStatus({ activity:'inactive', status:'inactive', confidence:confidence(false) }), 'Inactive');
  assert.equal(displayStatus(active('too_quiet', -2.4)), 'Too Quiet');
});
test('marks stale data without treating it as fresh', () => {
  assert.equal(freshness({ published_monotonic_s:5, quality:{ stale:true } }, 8), '3.0 s old — stale; do not act');
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
