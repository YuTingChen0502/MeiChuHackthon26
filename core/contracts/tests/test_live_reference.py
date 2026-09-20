"""User-approved policy extension; legacy fixtures remain valid and distinct."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import ValidationError
from core.contracts.validation import (
    ANALYZER, SETUP, WIRE, validate_record, validate_snapshot,
    validate_analyzer_pair, validate_command_binding, reference_binding,
)

FIXTURES = json.loads((Path(__file__).resolve().parents[3] /
                       'contracts/examples/pa_shared_v1.json').read_text())


def live_snapshot():
    s = copy.deepcopy(FIXTURES['rehearsal_snapshot'])
    s.update(workflow_policy='live_reference_v1', session_mode='live', latest_frame=None,
             active_baseline=None, perception=[])
    s['song'].update(workflow_state='LIVE_MONITORING', baseline_id=None)
    s['capture'] = dict(state='listening', source_generation=1,
                        requested_microphone_id=None,
                        logical_microphone_id='system-default', name='System default',
                        native_device_id=s['source']['input_asset_or_device_id'],
                        clock_id=s['source']['clock_id'], analysis_run_id='run-new',
                        frame_fresh=False, timestamp_mode='sample_count', operation_id=None,
                        switch_result='none', reason_codes=[])
    return s


class LiveReferenceContracts(unittest.TestCase):
    def test_policy_discriminator_preserves_legacy_requires_new_status(self):
        for name in ('live_snapshot', 'rehearsal_snapshot'):
            validate_snapshot(FIXTURES[name])
        s = live_snapshot()
        validate_snapshot(s)
        del s['capture']
        with self.assertRaises(ValidationError):
            validate_snapshot(s)
        s = live_snapshot()
        del s['workflow_policy']
        with self.assertRaises(ValueError):
            validate_snapshot(s)

    def test_live_analyzer_accepts_reference_without_changing_evidence_shape(self):
        c = copy.deepcopy(FIXTURES['analyzer_context'])
        e = copy.deepcopy(FIXTURES['source_level_deltas'])
        c['observation_purpose'] = 'live'
        c['probe_instrument_id'] = None
        c['target'].update(target_kind='reference', baseline=None)
        e['target'] = copy.deepcopy(c['target'])
        validate_analyzer_pair(c, e)

    def test_minimal_setup_and_logical_inventory(self):
        request = dict(song_id='song-1', reference_id='reference-1', workflow_policy='live_reference_v1')
        validate_record(request, SETUP, 'CreateSessionRequest')
        del request['workflow_policy']
        with self.assertRaises(ValidationError):
            validate_record(request, SETUP, 'CreateSessionRequest')
        validate_record(dict(devices=[], discovery_status='available', default_microphone_id='system-default',
                             microphones=[dict(microphone_id='system-default', name='Default microphone',
                                               is_default=True, selection_kind='system_default', grouping='system_route')]),
                        SETUP, 'AudioDevicesResponse')

    def test_switch_binds_current_source_generation_and_rejects_extra_payload(self):
        s = live_snapshot()
        c = dict(record_type='SessionCommand', schema_version='1.0', session_id=s['session_id'],
                 idempotency_key='switch-1', expected_state_version=s['state_version'],
                 reference=reference_binding(s['active_reference']), baseline=None, event=None,
                 action='switch_microphone', payload=dict(microphone_id='mic-usb', expected_source_generation=1))
        validate_command_binding(c, s)
        c['payload']['expected_source_generation'] = 0
        with self.assertRaises(ValueError):
            validate_command_binding(c, s)
        c['payload']['clock_id'] = 'client-clock'
        with self.assertRaises(ValidationError):
            validate_record(c, WIRE, 'SessionCommand')

    def test_old_source_frame_and_false_detection_rejected(self):
        s = live_snapshot()
        frame = dict(record_type='AnalysisFrame', schema_version='1.0', example_only=True,
                     frame_id='frame-test', session_id=s['session_id'], analysis_run_id='run-new',
                     sequence=1, input_kind=s['source']['input_kind'],
                     input_asset_or_device_id=s['source']['input_asset_or_device_id'],
                     clock_id=s['source']['clock_id'], sample_rate_hz=48000, sample_start=0,
                     sample_end=48000, capture_end_monotonic_s=100, published_monotonic_s=100,
                     model_bundle_id='example', frontend_id='example', execution_profile_id='example',
                     baseline_id=None, baseline_version=None, reference_id=s['active_reference']['reference_id'],
                     quality=dict(clipped_fraction=0, dropout=False, stale=False, comparability='comparable',
                                  capture_compatible=True, reason_codes=[], snr_estimate_db=None, snr_is_ground_truth=False),
                     observed_mix_level_delta_db=None, common_mode_gain_db=None,
                     identifiability_assumption='unresolved', inference_wall_ms=1,
                     instruments=[dict(record_type='InstrumentState', schema_version='1.0', instrument_id='bass',
                                       family='bass', activity='active', presence_probability=None,
                                       source_level_delta_db=None, balance_deviation_db=None, status='unknown', tone=None,
                                       confidence=dict(record_type='ConfidenceState', schema_version='1.0',
                                                       calibration_status='uncalibrated', calibration_id=None,
                                                       probability_event='not_available', magnitude_tolerance_db=2,
                                                       probability=None, prediction_interval_db=None, abstained=True,
                                                       reasons=['test_uncalibrated']))])
        s['latest_frame'] = frame
        s['capture'].update(state='active', frame_fresh=True, analysis_run_id=frame['analysis_run_id'])
        s['source'] = {key: frame[key] for key in ('input_kind', 'input_asset_or_device_id', 'clock_id')}
        s['capture']['clock_id'] = frame['clock_id']
        validate_snapshot(s)
        for key in ('clock_id', 'analysis_run_id', 'input_asset_or_device_id'):
            bad = copy.deepcopy(s)
            bad['latest_frame'][key] = 'old-source'
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_snapshot(bad)
        instrument = frame['instruments'][0]
        s['perception'] = [dict(instrument_id=instrument['instrument_id'], family=instrument['family'],
                                state='detected', frame_id=frame['frame_id'], reason_codes=[],
                                activity='active', observability='observable', validity='valid',
                                calibration_status='uncalibrated', action_abstained=True, numerical_advice_allowed=False)]
        instrument['confidence']['abstained'] = True
        instrument['confidence']['reasons'] = ['test_uncalibrated']
        validate_snapshot(s)  # Perception can be detected while PA advice is withheld.
        hinted = copy.deepcopy(s)
        hinted['latest_frame']['identifiability_assumption'] = 'majority_active_sources_unchanged'
        hinted['perception'][0]['state'] = 'uncertain'
        hinted['perception'][0]['adjustment_hint'] = dict(
            direction='reduce_level', status='experimental', basis='relative_balance',
            evidence_frame_id=frame['frame_id'], reason_codes=['uncalibrated_estimate'],
            automatic_execution=False)
        validate_snapshot(hinted)  # Direction does not authorize numerical advice.
        timed = copy.deepcopy(hinted)
        timed['analysis_timing'] = dict(profile_id='candidate_delayed_v1', queue_max_age_s=2,
            result_max_age_s=20, hint_hold_s=10, receipt_max_age_s=12, snapshot_monotonic_s=106)
        timed['latest_frame']['published_monotonic_s'] = 106
        timed['perception'][0]['adjustment_hint']['expires_monotonic_s'] = 116
        validate_snapshot(timed)
        for deadline in (106, 121, float('inf')):
            bad = copy.deepcopy(timed)
            bad['perception'][0]['adjustment_hint']['expires_monotonic_s'] = deadline
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                validate_snapshot(bad)
        bad = copy.deepcopy(timed)
        del bad['perception'][0]['adjustment_hint']['expires_monotonic_s']
        with self.assertRaises(ValueError): validate_snapshot(bad)
        bad = copy.deepcopy(timed)
        bad['analysis_timing']['queue_max_age_s'] = 20
        with self.assertRaises(ValidationError): validate_snapshot(bad)
        bad = copy.deepcopy(timed)
        bad['analysis_timing']['profile_id'] = 'strict_v1'
        with self.assertRaises(ValidationError): validate_snapshot(bad)
        for key, value in (('calibration_status', 'calibrated'),
                           ('calibration_status', 'out_of_envelope'),
                           ('action_abstained', False), ('numerical_advice_allowed', True)):
            bad = copy.deepcopy(hinted)
            bad['perception'][0][key] = value
            with self.subTest(hint_confidence=(key, value)), self.assertRaises(ValueError):
                validate_snapshot(bad)
        for key, value in (('stale', True), ('dropout', True), ('clipped_fraction', .1),
                           ('capture_compatible', False), ('comparability', 'weak')):
            bad = copy.deepcopy(hinted)
            bad['latest_frame']['quality'][key] = value
            with self.subTest(hint_quality=key), self.assertRaises(ValueError):
                validate_snapshot(bad)
        for key, value in (('evidence_frame_id', 'old-frame'), ('automatic_execution', True),
                           ('suggested_step_db', 2), ('probability', .9)):
            bad = copy.deepcopy(hinted)
            bad['perception'][0]['adjustment_hint'][key] = value
            with self.subTest(hint_field=key), self.assertRaises((ValueError, ValidationError)):
                validate_snapshot(bad)
        for key, value in (('activity', 'unknown'), ('validity', 'invalid'),
                           ('observability', 'not_observable')):
            bad = copy.deepcopy(hinted)
            bad['perception'][0][key] = value
            with self.subTest(hint_measurement=key), self.assertRaises(ValueError):
                validate_snapshot(bad)
        bad = copy.deepcopy(hinted)
        bad['latest_frame']['identifiability_assumption'] = 'unresolved'
        with self.assertRaises(ValueError):
            validate_snapshot(bad)
        for key, value in (('validity', 'invalid'), ('observability', 'unknown'),
                           ('activity', 'inactive'), ('numerical_advice_allowed', True)):
            bad = copy.deepcopy(s)
            bad['perception'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_snapshot(bad)
        s = live_snapshot()
        s['perception'] = [dict(instrument_id='bass', family='bass', state='detected', frame_id=None, reason_codes=[],
                                activity='active', observability='observable', validity='valid',
                                calibration_status='uncalibrated', action_abstained=True, numerical_advice_allowed=False)]
        with self.assertRaises(ValueError):
            validate_snapshot(s)


if __name__ == '__main__':
    unittest.main()
